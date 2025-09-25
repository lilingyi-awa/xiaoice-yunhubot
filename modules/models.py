import vetariasn as vt
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

class ChatMessageModel(vt.orm.Base):
    __tablename__ = "chat_message"
    seq: int = sa.Column(sa.BigInteger(), default=vt.algo.calc_seqid, primary_key=True)
    bot: str = sa.Column(sa.String(100), primary_key=True)
    user: int = sa.Column(sa.BigInteger(), primary_key=True)
    query: str = sa.Column(sa.Text(), nullable=False)
    answer: str = sa.Column(sa.Text(), nullable=False)
    vector: list[float] = Vector(dim=2048)