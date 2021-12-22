from functools import cache
from io import StringIO

import pandas as pd

import requests

COUNTRY_CODES_URL = "https://datahub.io/core/country-codes/r/country-codes.csv"


@cache
def get_eu_countries():
    """
    All EU ISO-2 codes

    Returns:
        data (list): List of ISO-2 codes)
    """
    url = "https://restcountries.eu/rest/v2/regionalbloc/eu"
    r = requests.get(url)
    return [row["alpha2Code"] for row in r.json()]


@cache
def get_continent_lookup():
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
def get_country_continent_lookup():
    """
    Retrieves continent lookups for all world countries,
    by ISO2 code, from a static open URL.

    Returns:
        data (dict): Values are country_name-continent pairs.
    """
    r = requests.get(COUNTRY_CODES_URL)
    r.raise_for_status()
    with StringIO(r.text) as csv:
        df = pd.read_csv(
            csv, usecols=["ISO3166-1-Alpha-2", "Continent"], keep_default_na=False
        )
    data = {
        row["ISO3166-1-Alpha-2"]: row["Continent"]
        for _, row in df.iterrows()
        if not pd.isnull(row["ISO3166-1-Alpha-2"])
    }
    # Kosovo, null
    data["XK"] = "EU"
    data[None] = None
    return data


@cache
def get_country_region_lookup():
    """
    Retrieves subregions (around 18 in total)
    lookups for all world countries, by ISO2 code,
    from a static open URL.

    Returns:
        data (dict): Values are country_name-region_name pairs.
    """
    r = requests.get(COUNTRY_CODES_URL)
    r.raise_for_status()
    with StringIO(r.text) as csv:
        df = pd.read_csv(
            csv, usecols=["official_name_en", "ISO3166-1-Alpha-2", "Sub-region Name"]
        )
    data = {
        row["ISO3166-1-Alpha-2"]: (row["official_name_en"], row["Sub-region Name"])
        for _, row in df.iterrows()
        if not pd.isnull(row["official_name_en"])
        and not pd.isnull(row["ISO3166-1-Alpha-2"])
    }
    data["XK"] = ("Kosovo", "Southern Europe")
    data["TW"] = ("Kosovo", "Eastern Asia")
    return data


@cache
def get_iso2_to_iso3_lookup(reverse=False):
    """
    Retrieves lookup of ISO2 to ISO3 (or reverse).

    Args:
        reverse (bool): If True, return ISO3 to ISO2 lookup instead.
    Returns:
        lookup (dict): Key-value pairs of ISO2 to ISO3 codes (or reverse).
    """
    country_codes = pd.read_csv(COUNTRY_CODES_URL)
    alpha2_to_alpha3 = {
        row["ISO3166-1-Alpha-2"]: row["ISO3166-1-Alpha-3"]
        for _, row in country_codes.iterrows()
    }
    alpha2_to_alpha3[None] = None  # no country
    alpha2_to_alpha3["XK"] = "RKS"  # kosovo
    if reverse:
        alpha2_to_alpha3 = {v: k for k, v in alpha2_to_alpha3.items()}
    return alpha2_to_alpha3


@cache
def get_disputed_countries():
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
