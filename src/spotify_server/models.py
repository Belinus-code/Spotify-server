from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Table
from sqlalchemy.orm import relationship, declarative_base, Mapped, mapped_column

Base = declarative_base()

# --- Linktabelle Track <-> Artist ---
track_artists = Table(
    'track_artist', Base.metadata,
    Column('track_id', String(100), ForeignKey('track.track_id', ondelete="CASCADE"), primary_key=True),
    Column('artist_id', Integer, ForeignKey('artist.artist_id', ondelete="CASCADE"), primary_key=True)
)


class User(Base):
    __tablename__ = 'user'
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))

    training_data = relationship("TrainingData", back_populates="user", cascade="all, delete-orphan")


class Artist(Base):
    __tablename__ = 'artist'
    artist_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))

    tracks = relationship("Track", secondary=track_artists, back_populates="artists")


class Track(Base):
    __tablename__ = 'track'
    track_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    year: Mapped[int] = mapped_column(Integer, default=-1)
    popularity: Mapped[int] = mapped_column(Integer, default=0)

    artists = relationship("Artist", secondary=track_artists, back_populates="tracks")
    playlists = relationship("PlaylistTrack", back_populates="track")
    training_data = relationship("TrainingData", back_populates="track")


class Playlist(Base):
    __tablename__ = 'playlist'
    playlist_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))

    tracks = relationship("PlaylistTrack", back_populates="playlist")
    training_data = relationship("TrainingData", back_populates="playlist")


class PlaylistTrack(Base):
    __tablename__ = 'playlist_track'
    playlist_id: Mapped[str] = mapped_column(String(100), ForeignKey('playlist.playlist_id', ondelete="CASCADE"), primary_key=True)
    track_id: Mapped[str] = mapped_column(String(100), ForeignKey('track.track_id', ondelete="CASCADE"), primary_key=True)

    playlist = relationship("Playlist", back_populates="tracks")
    track = relationship("Track", back_populates="playlists")


class TrainingData(Base):
    __tablename__ = 'training_data'
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('user.user_id', ondelete="CASCADE"), primary_key=True)
    playlist_id: Mapped[str] = mapped_column(String(100), ForeignKey('playlist.playlist_id', ondelete="CASCADE"), primary_key=True)
    track_id: Mapped[str] = mapped_column(String(100), ForeignKey('track.track_id', ondelete="CASCADE"), primary_key=True)

    correct_guesses: Mapped[int] = mapped_column(Integer, default=0)
    correct_in_row: Mapped[int] = mapped_column(Integer, default=0)
    repeat_in_n: Mapped[int] = mapped_column(Integer, default=1)
    revisions: Mapped[int] = mapped_column(Integer, default=0)
    is_done: Mapped[int] = mapped_column(Boolean, default=False)

    user = relationship("User", back_populates="training_data")
    playlist = relationship("Playlist", back_populates="training_data")
    track = relationship("Track", back_populates="training_data")


class TrackArtist(Base):
    __tablename__ = "track_artists"
    track_id: Mapped[str] = mapped_column(String(100), ForeignKey("track.track_id"), primary_key=True)
    artist_id: Mapped[int] = mapped_column(Integer, ForeignKey("artist.artist_id"), primary_key=True)
