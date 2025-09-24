import asyncio
import vetariasn as vt
import sqlalchemy as sa

class SystemLogModel(vt.orm.Base):
    __tablename__ = "admin_logs"
    seq: int = sa.Column(sa.BigInteger(), default=vt.algo.calc_seqid, primary_key=True)
    claimTo: int = sa.Column(sa.BigInteger(), default=0, primary_key=True)
    content: dict = sa.Column(sa.JSON(), nullable=False)

async def __log(log: SystemLogModel):
    for retry_time in range(0, 5):
        try:
            async with vt.orm.Session() as sess:
                sess.add(log)
                await sess.commit()
            return
        except Exception:
            await asyncio.sleep(1 << retry_time)

def record_log(content: str, claimTo: int = 0):
    asyncio.create_task(__log(SystemLogModel(content=content, claimTo=claimTo)))