import enum
import logging
from datetime import datetime
from sqlalchemy import Column, Enum, Integer, Unicode, ForeignKey, create_engine
from sqlalchemy import CheckConstraint, orm
from sqlalchemy import DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy_repr import RepresentableBase


class TaskSource(enum.Enum):
    system = 1
    twitch = 2
    discord = 3


Session = orm.sessionmaker()

log = logging.getLogger("roboto.model")
log.setLevel(logging.DEBUG)

Base = declarative_base(cls=RepresentableBase)


class User(Base):
    __tablename__ = 'user'

    user_id = Column(Integer, primary_key=True)
    discord_id = Column(Integer, unique=True, nullable=True)
    twitch_id = Column(Unicode, unique=True, nullable=True)
    created_on = Column(DateTime, nullable=False, default=datetime.now())

    __table_args__ = (
        # We must have at least one ID
        CheckConstraint('discord_id or twitch_id', name="check_user_id"),
    )

    @staticmethod
    def get(session: orm.Session, discord_id=None, user_id=None, twitch_id=None, create=True):
        """

        :param session:
        :param discord_id:
        :param user_id:
        :param twitch_id:
        :param create:
        :rtype: roboto.model.User
        :return:
        """
        if not any([discord_id, user_id, twitch_id]):
            return None
        q = session.query(User)
        if user_id:
            col = User.user_id
            val = user_id
        elif twitch_id:
            col = User.twitch_id
            val = twitch_id.lower()
        else:
            col = User.discord_id
            val = discord_id
        q = q.filter(col == val).first()
        if q:
            return q
        if create:
            user = User()
            setattr(user, col.key, val)
            session.add(user)
            log.debug("Creating new user: {}".format(user))
            return user
        return None


class UserMessage(Base):
    __tablename__ = "user_messages"

    msg_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey(User.user_id), nullable=False)
    source_id = Column(Enum(TaskSource), nullable=False)
    channel = Column(Unicode, nullable=False)
    content = Column(Unicode, nullable=False)
    created_on = Column(DateTime, default=datetime.now())

    user = relationship("User")

    @classmethod
    def record(cls, session, user, source, channel, message):
        msg = cls()
        msg.user = user
        msg.source_id = source
        msg.content = message
        msg.channel = channel
        session.add(msg)


def init_db(config):
    opts = {
        "encoding": "utf-8"
    }
    dsn = config.get("dsn", None)
    if not dsn:
        log.warning("Using temporary database, expect total data lost on shutdown..")
        dsn = "sqlite://"
    if "sqlite" not in dsn:
        opts.update(dict(pool_size=20, pool_recycle=3600))
    engine = create_engine(dsn, echo=True, **opts)
    Base.metadata.create_all(engine)
    Session.configure(bind=engine)
    log.debug("Configured database")



