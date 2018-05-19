
from enum import Enum
from typing import NamedTuple

import maya


class TransactionType(Enum):
    ORDER = "order"
    SEARCH = "search"
    VIEW = "view"
    REGISTRATION = "registration"
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
        else:
            return cls.OTHER


class Transaction(NamedTuple):
    transaction_type: TransactionType
    timestamp: maya.MayaDT
    customer: str
    location: str
    brand: str
    product: str
    price: str
    searchterm: str