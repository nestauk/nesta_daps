"""
country iso codes
=================

tools for lookup of iso codes for countries
"""

import pycountry
from functools import lru_cache
from pycountry_convert import country_alpha2_to_continent_code


def alpha2_to_continent_mapping():
    """Wrapper around :obj:`pycountry-convert`'s :obj:`country_alpha2_to_continent_code`
    function to generate a dictionary mapping ISO2 to continent codes, accounting
    where :obj:`pycountry-convert` has no mapping (e.g. for Vatican).

    Returns:
        :obj`dict`
    """
    continents = {}
    for c in pycountry.countries:
        continents[c.alpha_2] = None
        try:
            continents[c.alpha_2] = country_alpha2_to_continent_code(c.alpha_2)
        except KeyError:
            pass
    return continents


def _country_iso_code(country):
    for name_type in ["name", "common_name", "official_name"]:
        query = {name_type: country}
        try:
            result = pycountry.countries.get(**query)
            if result is not None:
                return result
        except KeyError:
            pass
    raise KeyError(f"{country} not found")


@lru_cache()
def country_iso_code(country):
    """
    Look up the ISO 3166 codes for countries.
    https://www.iso.org/glossary-for-iso-3166.html

    Wraps the pycountry module to attempt lookup with all name options.

    Args:
        country (str): name of the country to lookup
    Returns:
        Country object from the pycountry module
    """
    country = str(country)
    try:
        # Note this will raise KeyError if fails
        result = _country_iso_code(country)
    except KeyError:
        # Note this will raise KeyError if fails
        result = _country_iso_code(country.title())
    return result


def country_iso_code_list(list, country="country"):
    """
    A wrapper for the country_iso_code function to apply it to a whole dataframe,
    using the country name. Also appends the continent code based on the country.

    Args:
        list (:obj:`list`): a list of dicts containing a country field.
        country (str): field in df containing the country name
    Returns:
        a list of dicts with country_alpha_2, country_alpha_3, country_numeric, and
        continent columns appended.
    """

    continents = alpha2_to_continent_mapping()
    country_codes = None
    for item in list:
        item["country_alpha_2"] = None
        item["country_alpha_3"] = None
        item["country_numeric"] = None
        item["continent"] = None
        try:
            country_codes = country_iso_code(item[country])
        except KeyError:
            # some fallback method could go here
            continue
        else:
            if country_codes is None:
                continue
        item["country_alpha_2"] = country_codes.alpha_2
        item["country_alpha_3"] = country_codes.alpha_3
        item["country_numeric"] = country_codes.numeric
        item["continent"] = continents.get(country_codes.alpha_2)
    return list


def country_iso_code_to_name(code, iso2=False):
    """Converts country alpha_3 into name and catches error so this can be used with
       pd.apply.

    Args:
        code (str): iso alpha 3 code
        iso2 (bool): use alpha 2 code instead
    Returns:
        str: name of the country or None if not valid
    """
    try:
        if iso2:
            return pycountry.countries.get(alpha_2=code).name
        else:
            return pycountry.countries.get(alpha_3=code).name
    except (KeyError, AttributeError):
        return None
