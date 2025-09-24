import aiohttp
from modules.config import config
import typing

class YunhuMessage:
    def __init__(self, bot: str, target: int):
        self.__bot = bot
        self.__msgid = ""
        self.__content = ""
        self.__is_modified = False
        self.__target = target
        self.__buttons: dict[str, typing.Any] = {}
        self.__contentType: typing.Literal["text", "markdown", "html"] = "text"
    # content
    @property
    def content(self):
        return self.__content
    @content.setter
    def content(self, value: str):
        self.__content = value
        self.__is_modified = True
    # buttons
    @property
    def buttons(self):
        return self.__buttons
    @buttons.setter
    def buttons(self, value: dict[str, typing.Any]):
        self.__buttons = value
        self.__is_modified = True
    # contentType
    @property
    def contentType(self):
        return self.__contentType
    @contentType.setter
    def contentType(self, value: typing.Literal["text", "markdown", "html"]):
        self.__contentType = value
        self.__is_modified = True
    # commit
    async def commit(self):
        if not self.__is_modified:
            return
        async with aiohttp.ClientSession() as sess:
            if self.__msgid == "":
                result = await (await sess.post(
                    url=f"https://chat-go.jwzhd.com/open-apis/v1/bot/send?token={config.bot[self.__bot].apikey}",
                    json={
                        "recvId": str(self.__target),
                        "recvType": "user",
                        "contentType": self.__contentType,
                        "content": {
                            "text": self.__content,
                            "buttons": self.__buttons
                        }
                    }
                )).json()
                self.__msgid = result["data"]["messageInfo"]["msgId"]
            else:
                result = await sess.post(
                    url=f"https://chat-go.jwzhd.com/open-apis/v1/bot/edit?token={config.bot[self.__bot].apikey}",
                    json={
                        "msgId": self.__msgid,
                        "recvId": str(self.__target),
                        "recvType": "user",
                        "contentType": self.__contentType,
                        "content": {
                            "text": self.__content,
                            "buttons": self.__buttons
                        }
                    }
                )
        self.__is_modified = False

class YunhuContext(YunhuMessage):
    def __init__(self, bot, target):
        self.__frombot = bot
        self.__touser = target
        super().__init__(bot, target)
        self.content = "正在生成中，请稍后..."
    async def __aenter__(self):
        await self.commit()
        return self
    async def __aexit__(self, exc_type, exc, tb):
        if exc_type:
            print(f"Error detected: {type(exc).__name__}: {repr(exc)} (Bot: {self.__frombot}) (UID: {self.__touser})")
            try:
                self.content = f"系统错误：{type(exc).__name__}: {repr(exc)}"
                await self.commit()
            except Exception as e2:
                print(f"Error detected: {type(e2).__name__}: {repr(e2)} (Bot: {self.__frombot}) (UID: {self.__touser})")
        else:
            try:
                await self.commit()
            except Exception as exc:
                print(f"Error detected: {type(e2).__name__}: {repr(e2)} (Bot: {self.__frombot}) (UID: {self.__touser})")
        