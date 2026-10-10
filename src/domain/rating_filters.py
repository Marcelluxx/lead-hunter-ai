"""User-supplied criteria only; provider metrics never enter this contract."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class RatingFilterCriteria:
    min_rating: float = 3.9
    max_reviews: int = 100

    def __post_init__(self) -> None:
        if (type(self.min_rating) not in (int, float) or
                not 0 <= self.min_rating <= 5 or not math.isfinite(self.min_rating) or
                type(self.max_reviews) is not int or not 1 <= self.max_reviews <= 2147483647):
            raise ValueError('rating_filter_invalid')
        object.__setattr__(self, 'min_rating', float(self.min_rating))
