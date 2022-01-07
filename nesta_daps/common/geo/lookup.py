from functools import cache
from io import StringIO

import csv

import requests

COUNTRY_CODES_URL = "https://datahub.io/core/country-codes/r/country-codes.csv"


@cache
def get_eu_countries() -> list:
    """
    All EU ISO-2 codes

    Returns:
        data (list): List of ISO-2 codes)
    """
    url = "https://restcountries.eu/rest/v2/regionalbloc/eu"
    r = requests.get(url)
    return [row["alpha2Code"] for row in r.json()]


@cache
def get_continent_lookup() -> list:
    """
    Retrieves continent ISO2 code to continent name mapping from a static open URL.

    Returns:
        data (dict): Key-value pairs of continent-codes and names.
    """

    url = (
        "https://nesta-open-data.s3.eu-west"
        "-2.amazonaws.com/rwjf-viz/"
        "continent_codes_names.json"
    )
    continent_lookup = {row["Code"]: row["Name"] for row in requests.get(url).json()}
    continent_lookup[None] = None
    continent_lookup[""] = None
    return continent_lookup


@cache
def get_country_continent_lookup() -> dict:
    """
    Retrieves continent lookups for all world countries,
    by ISO2 code, from a static open URL.

    Returns:
        data (dict): Values are country_name-continent pairs.
    """
    r = requests.get(COUNTRY_CODES_URL)
    r.raise_for_status()
    with StringIO(r.text) as country_codes_csv:
        country_codes = [{
                k: v for k, v in row.items()
            }
            for row in csv.DictReader(country_codes_csv)]
    data = {
        item["ISO3166-1-Alpha-2"]: item["Continent"]
        for item in country_codes
        if item["ISO3166-1-Alpha-2"] is not None
    }
    # Kosovo, null
    data["XK"] = "EU"
    data[None] = None
    return data


@cache
def get_country_region_lookup() -> dict:
    """
    Retrieves subregions (around 18 in total)
    lookups for all world countries, by ISO2 code,
    from a static open URL.

    Returns:
        data (dict): Values are country_name-region_name pairs.
    """
    r = requests.get(COUNTRY_CODES_URL)
    r.raise_for_status()
    with StringIO(r.text) as country_codes_csv:
        country_codes = [{
                k: v for k, v in row.items()
            }
            for row in csv.DictReader(country_codes_csv)]
    data = {
        item["ISO3166-1-Alpha-2"]: (item["official_name_en"], item["Sub-region Name"])
        for item in country_codes
        if len(item["official_name_en"]) > 0
        and len(item["ISO3166-1-Alpha-2"]) > 0
    }
    data["XK"] = ("Kosovo", "Southern Europe")
    data["TW"] = ("Kosovo", "Eastern Asia")
    return data


@cache
def get_iso2_to_iso3_lookup(reverse: bool=False) -> dict:
    """
    Retrieves lookup of ISO2 to ISO3 (or reverse).

    Args:
        reverse (bool): If True, return ISO3 to ISO2 lookup instead.
    Returns:
        lookup (dict): Key-value pairs of ISO2 to ISO3 codes (or reverse).
    """
    r = requests.get(COUNTRY_CODES_URL)
    r.raise_for_status()
    with StringIO(r.text) as country_codes_csv:
        country_codes = [{
            k: v for k, v in row.items()
        }
        for row in csv.DictReader(country_codes_csv)]
    alpha2_to_alpha3 = {
        code_item["ISO3166-1-Alpha-2"]: code_item["ISO3166-1-Alpha-3"]
        for code_item in country_codes
    }
    alpha2_to_alpha3[None] = None  # no country
    alpha2_to_alpha3["XK"] = "RKS"  # kosovo
    if reverse:
        alpha2_to_alpha3 = {v: k for k, v in alpha2_to_alpha3.items()}
    return alpha2_to_alpha3


@cache
def get_disputed_countries() -> dict:
    """Lookup of disputed aliases, to "forgive" disperate datasets
    for making different geo-political decisions

    Returns:
        lookup (dict):
    """
    return {
        "RKS": "SRB",  # Kosovo: Serbia
        "TWN": "CHN",  # Taiwan: China
        "HKG": "CHN",  # Hong Kong: China
        "ROU": "ROM",
    }  # not disputed: just inconsistent format for Romania
