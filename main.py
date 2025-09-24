import os
from modules.config import config
os.environ.update(config.server)
from modules.chating import aichat
from modules.yunhu import YunhuMessage
from modules.logs import record_log
import vetariasn as vt
from modules.validator import validate
from fastapi import Request

async def response(uid: int, bot: str, content: str):
    try:
        msg = YunhuMessage(bot=bot, target=uid)
        msg.content = content
        await msg.commit()
    except Exception:
        pass

async def accept_request(uid: int, bot: str, content: str):
    try:
        async with vt.mutex.MutexContext(lock=f"yunhu:cv:{hex(uid)}", ttl=1200):
            await aichat(bot=bot, target=7261230, query=content)
    except vt.mutex.ConflictError:
        record_log({"type": "conversation.reetrant"}, claimTo=uid)

@vt.http.post("/yunhu-webhook")
async def webhook(w: Request, bot: str, secret: str):
    if bot not in config.bot or config.bot[bot].secret != secret:
        return
    ts = await w.json()
    if validate(ts, {
        "header::eventType": "message.receive.normal",
        "event::chat::chatType": "bot",
        "event::message::contentType": ("text", "markdown")
    }):
        vt.create_task(accept_request(
            uid=int(ts["event"]["sender"]["senderId"]),
            bot=bot,
            content=ts["event"]["message"]["content"]["text"]
        ))

vt.run()