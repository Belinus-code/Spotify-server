"""Module for Data Transfer Objects (DTOs) used in the application."""


class SongDTO:
    """DTO for transferring song data"""

    def __init__(
        self, track_id: int, title: str, artists: list[str], year: int, popularity=0
    ):
        self.track_id = track_id
        self.title = title
        self.name = title  # Alias for compatibility
        self.artists = artists
        self.year = year
        self.popularity = popularity
