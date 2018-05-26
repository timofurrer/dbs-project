"""
Module to geocode location information
"""

import logging

from geopy.geocoders import Nominatim

#: Holds the logger for scraping
logger = logging.getLogger('geocoding')
logging.basicConfig(level=logging.DEBUG)


def geocode(location):
    geolocator = Nominatim()
    loc = geolocator.geocode(location)
    logger.debug("Geocoded location %s to %s", location, loc)
    if loc is None:
        # get default location if not found
        loc = geolocator.geocode("Switzerland")

    return {
            "address": loc.address,
            "lng": loc.longitude,
            "lat": loc.latitude
    }
