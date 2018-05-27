
from enum import Enum
from typing import NamedTuple

import maya


class TransactionType(Enum):
    ORDER = "order"
    SEARCH = "search"
    VIEW = "view"
    REGISTRATION = "registration"
    DELIVERY = "delivery"
    PICKUP = "pickup"
    RATED = "rated"
    ANSWERING = "answering"
    OTHER = "other"

    @classmethod
    def identify(cls, text):
        if "just ordered" in text:
            return cls.ORDER
        elif "is looking for" in text:
            return cls.SEARCH
        elif "is looking at" in text:
            return cls.VIEW
        elif "just registered as a" in text:
            return cls.REGISTRATION
        elif "was sent to" in text:
            return cls.DELIVERY
        elif "is collecting" in text:
            return cls.PICKUP
        elif "rated" in text:
            return cls.RATED
        elif "is answering":
            return cls.ANSWERING
        else:
            return cls.OTHER


class Transaction(NamedTuple):
    transaction_type: TransactionType
    timestamp: maya.MayaDT
    customer: str
    location: str
    brand: str
    product: str
    price: float
    currency: str
    text: str
    raw: str
