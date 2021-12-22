"""
Get GTR data
============

Extract all Gateway To Research data via
the official API, unpacking all data recursively through
project entities.
"""

import re
from collections import defaultdict

import defusedxml.etree.ElementTree

from nesta_daps.geo.geocode import _geocode
from nesta_daps.geo.iso import alpha2_to_continent_mapping
from nesta_daps.geo.iso import country_iso_code

import requests

from retrying import retry


# Global constants
TOP_URL = "https://gtr.ukri.org/gtr/api/projects"
TOTALPAGES_KEY = "{http://gtr.rcuk.ac.uk/gtr/api}totalPages"
REGEX = re.compile(r"\{(.*)\}(.*)")
REGEX_API = re.compile(r"https://gtr.ukri.org:443/gtr/api/(.*)/(.*)")


def extract_link_table(data):
    """Iterate through the collected data and generate the link table
    between entities and their associated project.

    Args:
        data (:obj:`defaultdict(list)`): Data holder, mapping entities to rows of data.
                                         Note: data is unpacked into this object.
    """
    link_table = []
    for table_name, rows in data.items():
        is_topic = table_name == "topic"
        for row in rows:
            project_id = None
            rel = "TOPIC" if is_topic else None
            if "project_id" in row:
                project_id = row.pop("project_id")
            if "rel" in row:
                rel = row.pop("rel")
            if project_id is None or rel is None:
                continue
            ### Added recently, check logic
            if "id" not in row:
                continue
            link_table.append(
                dict(
                    project_id=project_id,
                    rel=rel,
                    id=row["id"],
                    table_name=f"gtr_{table_name}",
                )
            )
    data["link_table"] = link_table


def is_list_entity(row_value):
    """All list entities have the following structure:

         {"key": [{<data>}]}

    so this function tests specifically this.

    Args:
        row_value: Object to test
    """
    if not isinstance(row_value, dict):
        return False
    if len(row_value) != 1:
        return False
    nested_value = next(iter(row_value.values()))
    return isinstance(nested_value, list)


def contains_key(d, search_key):
    """Does any generic mixed dict/list (i.e. json-like) object contain the key?

    Args:
        d (:obj:`json`): A mixed dict/list (i.e. json-like) object to query.
        search_key (:obj:`hashable`): A key to search for.
    Returns:
        (:obj:`True` or :obj:`False`)
    """
    if isinstance(d, list):
        return any(contains_key(item, search_key) for item in d)
    elif not isinstance(d, dict):
        return False
    return search_key in d or any(contains_key(d[k], search_key) for k in d)


def remove_last_occurence(s, to_remove):
    """Remove last occurence of :obj:`to_remove` from :obj:`s`."""
    li = s.rsplit(to_remove, 1)
    return "".join(li)


def is_iterable(x):
    """Is the argument an iterable?"""
    try:
        iter(x)
    except TypeError:
        return False
    return True


class TypeDict(dict):
    """dict-like class which converts string values to an
    appropriate type automatically."""

    def set_and_cast_item(self, k, v, _type):
        try:
            v = _type(v)
        except (ValueError, TypeError):
            return False
        super().__setitem__(k, v)
        return True

    def __setitem__(self, k, v):
        if v == {"nil": "true"} or v == float("inf"):
            return super().__setitem__(k, None)
        # Don't bother if not a string
        # or if all characters are letters
        if not isinstance(v, str) or v.replace(" ", "").isalpha():
            return super().__setitem__(k, v)
        # Try int and float
        if self.set_and_cast_item(k, v, int):
            return
        if self.set_and_cast_item(k, v, float):
            return
        # # Cycle through date formats
        # base_fmt = '%Y-%m-%d{}'
        # for time_fmt in ('', 'T%H:%M:%S', 'T%H:%M:%S%z', 'Z',
        #                  'T%H:%M:%SZ', 'T%H:%M:%S%zZ', '%z'):
        #     _v = remove_last_occurence(v, ':') if '%z' in time_fmt else v
        #     fmt = base_fmt.format(time_fmt)
        #     if self.set_and_cast_item(k, _v, lambda x: dt.strptime(x, fmt)):
        #         return
        # Otherwise, set as normal
        super().__setitem__(k, v)


def deduplicate_participants(data):
    """The participant data is a duplicate of organisation,
    with only two specific interesting fields. Unfortunately
    GtR doesn't use an easy naming convention which allows this
    procedure to be performed without hard-coding.

    Args:
        data (:obj:`defaultdict(list)`): Data holder, mapping entities to rows of data
    """
    # Iterate through participants and generate a composite key
    for row in data["participant"]:
        org_id = row.pop("organisationId")
        row["id"] = org_id + row["project_id"]
        row["organisation_id"] = org_id
        row["rel"] = row.pop("role")
        del row["organisationName"]

    # # Iterate through participants
    # for row in data.pop('participant'):
    #     # Find a matching organisation
    #     for _row in data['organisations']:
    #         if row['organisationId'] != _row['id']:
    #             continue
    #         # Extract the two specific bonus fields
    #         for key in ('projectCost', 'grantOffer'):
    #             _row[key] = row[key]
    #         # Stop iterating, since we've found the organisation
    #         break


def unpack_funding(row):
    """Unpack and flatten data from any 'dict' field containing the
    "currencyCode" key.

    Args:
        row (dict): A row of GtR data to unpack.
                    Note, the row will be changed if any "currencyCode" keys are found.
    """
    # Only unpack dicts
    if not isinstance(row, dict):
        return
    # Extract the keys to remove
    to_pop = [k for k, v in row.items() if isinstance(v, dict) and "currencyCode" in v]
    # Iterate and flatten
    for k in to_pop:
        fund_data = row.pop(k)
        for field, value in fund_data.items():
            row[field] = value


def unpack_list_data(row, data):
    """Unpack from GtR list-like data, and infer entities from them,
    with an associated project id for the link table.

    Args:
        row (dict): A row of GtR project data, within which there may be lists to unpack.
        data (:obj:`defaultdict(list)`): Data holder, mapping entities to rows of data.
                                         Note: data is unpacked into this object.
    """
    # Create a list of list-like data to unpack
    to_pop = [k for k, v in row.items() if is_list_entity(v)]
    # Iterate through keys
    for k in to_pop:
        # Pop out the entry, so that it can be entered into `data`
        # as a standalone entity
        dict_list = row.pop(k)
        # Special case: entities containing 'text' are topics
        is_topic = contains_key(dict_list, "text")
        # Iterate over the nested list
        key, nested_list = next(iter(dict_list.items()))
        for item in nested_list:
            table_name = key
            # Associate the table entry with a project id
            item["project_id"] = row["id"]
            # If the entity type has been provided then overwrite
            if "entity" in item:
                table_name = item.pop("entity")
            # If this is a topic field then apply common rules
            if is_topic:
                # The percentage variable mucks up the schema
                # and is anyway not super-interesting
                if "percentage" in item:
                    item.pop("percentage")
                item["topic_type"] = key
                table_name = "topic"
            data[table_name.replace("/", "_")].append(item)


def extract_link_data(url):
    """Enter a link URL and recursively extract the data.

    Args:
        url (str): A GtR URL from which to extract data.
    Returns:
        row (dict): Unpacked GtR data.
    """
    et = read_xml_from_url(url)
    row = TypeDict()
    # Note: Ignore any links and hrefs, as this will lead to
    # infinite recursion!
    if et is not None:
        extract_data_recursive(et, row, ignore=["links", "href"])
    return row


def extract_data(et, ignore=[]):
    """Generically extract and flatten any GtR entity.

    Args:
        et (:obj:`xml.etree.ElementTree`): A GtR XML entity "row".
        ignore (:obj:`list` of :obj:`str`): Ignore any entity types in this list.
    Returns:
        entity, row (str, dict): Entity type and data.
    """
    row = TypeDict()
    # Get the root entity name
    _, entity = REGEX.findall(et.tag)[0]
    if entity in ignore:
        return entity, row
    # Iterate over data fields
    for k, v in et.attrib.items():
        # Extract the field name
        _, field = REGEX.findall(k)[0]
        if field in ignore:
            continue
        # URLs need to be treated differently, as they point to new data
        if field == "href":
            # Get the ID and entity type of the object pointed to by the URL
            _entity, _id = REGEX_API.findall(v)[0]
            # ... then extract the data at that URL
            _entity_data = extract_link_data(v)
            # Finally, unpack the data as usual
            row["entity"] = _entity
            row["id"] = _id
            for _k, _v in _entity_data.items():
                row[_k] = _v
        # If the field appears multiple times, ignore it
        elif field in row:
            continue
        # Otherwise, this just is a simple flat field
        else:
            row[field] = v
    # If there is any text data, unpack it into a fake field called "value"
    if et.text not in (None, ""):
        row["value"] = et.text
    # If currency data is nested then unpack
    unpack_funding(row)
    return entity, row


def extract_data_recursive(et, row, ignore=[]):
    """Recursively dive into and extract a row of data.

    Args:
        et (:obj:`xml.etree.ElementTree`): A GtR XML entity "row".
        row (dict): The output row of data to fill.
        ignore: See :obj:`extract_data`.
    """
    for c in et.getchildren():
        # Extract the shallow data for this row
        entity, _row = extract_data(c, ignore)
        if entity in ignore:
            continue
        # Unpack any deep data into the shallow _row that we just extracted
        extract_data_recursive(c, _row, ignore)
        # If this row contains "value" or "item", and nothing else, then flatten it further
        # as these are dummy fields in the GtR data
        if isinstance(_row, dict):
            for key in ("value", "item"):
                if key in _row and len(_row) == 1:
                    _row = _row[key]
                    break
        # Ignore duplicate entries
        if entity in row and _row == row[entity]:
            continue
        # Treat 'link' objects differently: append as a list item to the parent row
        is_topic_row = isinstance(_row, dict) and "text" in _row
        if entity in ("link", "participant") or is_topic_row:
            if entity not in row:
                row[entity] = []
            row[entity].append(_row)
        # Otherwise, append any non-empty data to the parent row
        elif (not is_iterable(_row)) or len(_row) > 0:
            row[entity] = _row


@retry(wait_random_min=120, wait_random_max=300, stop_max_attempt_number=10)
def read_xml_from_url(url, **kwargs):
    """Read pure XML data directly from a URL.

    Args:
        url (str): The source URL.
        kwargs (dict): Any :obj:`params` data to pass to :obj:`requests.get`.
    Returns:
        An `:obj:`xml.etree.ElementTree` of the full XML tree.
    """
    r = requests.get(url, params=kwargs)
    if "Unable to find" in r.text:
        return None
    r.raise_for_status()
    et = defusedxml.etree.ElementTree.fromstring(r.text)
    return et


def get_orgs_to_process(all_orgs, existing_orgs):
    """Extracts organisations and addresses, flattens addresses and returns just records
    that have not prevously been processed.

    Args:
        all_orgs(:obj:`list` of :obj:`tuple`): organisation id and addresses
        existing_orgs(:obj:`list` of :obj:`tuple`): organisation ids

    Returns:
        (:obj: `list` of :obj:`dict`): organisations to process
    """
    # convert list of 1-tuples to a set
    existing_ids = {org_id for (org_id,) in existing_orgs}

    orgs_to_process = []
    for org in all_orgs:
        org_id, address = org

        if org_id not in existing_ids:
            org_details = {"id": org_id}
            if address is not None:
                org_details = {
                    **address["address"],
                    **org_details,
                }  # address also contains an 'id' which we overwrite with the id in org_details

            orgs_to_process.append(org_details)

    return orgs_to_process


def geocode_uk_with_postcode(org_details):
    """Wrapper for the geocoder that will process any organisations that are in the UK
    and have a postcode. Any that succeed also have their country overwritten, so the
    data in this column is consistent.

    Args:
        orgs_details (dict): organisation details, without latitude and longitude

    Returns
        (dict): processed org details with latitude, longitude appended
    """
    org_details["latitude"] = None
    org_details["longitude"] = None

    if (
        org_details.get("region") != "Outside UK"
        and org_details.get("postCode") is not None
    ):
        # assume most without 'Outside UK' region are UK, but hardcode country into the
        # request to prevent false results with identical postcodes that exist in multiple countries
        coordinates = _geocode(
            postalcode=org_details["postCode"], country="United Kingdom"
        )

        if coordinates is not None:
            org_details["latitude"] = coordinates["lat"]
            org_details["longitude"] = coordinates["lon"]
            # if geocode succeeds with country=United Kingdom then overwrite it
            org_details["country"] = "United Kingdom"

    return org_details


def add_country_details(org_details):
    """If country name is valid attempt to append iso codes and continent.

    Args:
        org_details (dict): organisation details, without iso codes and continent

    Returns:
        (dict): processed org with extra data appended or None if failure
    """
    continent_map = alpha2_to_continent_mapping()

    try:
        country_name = org_details["country"]
        country_codes = country_iso_code(country_name)
    except KeyError:
        for c in [
            "country_alpha_2",
            "country_alpha_3",
            "country_name",
            "country_numeric",
            "continent",
        ]:
            org_details[c] = None
    else:
        org_details["country_alpha_2"] = country_codes.alpha_2
        org_details["country_alpha_3"] = country_codes.alpha_3
        org_details["country_name"] = country_codes.name
        org_details["country_numeric"] = country_codes.numeric
        org_details["continent"] = continent_map[country_codes.alpha_2]

    return org_details


if __name__ == "__main__":

    # Local constants
    PAGE_SIZE = 100

    # Assertain the total number of pages first
    projects = read_xml_from_url(TOP_URL, p=1, s=PAGE_SIZE)
    total_pages = int(projects.attrib[TOTALPAGES_KEY])

    # The output data structure:
    # each key represents a unique flat entity (i.e. a flat 'table')
    # each list represents rows in that table.
    data = defaultdict(list)

    # Iterate through all pages
    for page in range(1, total_pages + 1):
        # Get all projects on this page
        projects = read_xml_from_url(TOP_URL, p=page, s=PAGE_SIZE)
        for project in projects.getchildren():
            # Extract the data for the project into 'row'
            _, row = extract_data(project)
            # Then recursively extract data from nested rows into the parent 'row'
            extract_data_recursive(project, row)
            # Flatten out any list data directly into 'data' under separate tables
            unpack_list_data(row, data)
            row.pop("identifiers")
            # Append the row
            data[row.pop("entity")].append(row)
            break
        break

    # The 'participant' data is near duplicate
    # of 'organisation' data so merge them.
    if "participant" in data:
        deduplicate_participants(data)

    for k, v in data.items():
        print(k)
        print(v)
        print()
