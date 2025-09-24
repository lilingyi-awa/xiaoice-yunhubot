import openai
from modules.config import config
import vetariasn as vt
import sqlalchemy as sa
from modules.models import ChatMessageModel
from modules.yunhu import YunhuContext
import aiohttp
import json
from modules.logs import record_log

client = openai.AsyncOpenAI(api_key=config.engine.moonshot_key, base_url="https://api.moonshot.cn/v1")

async def rerank(query: str, objects: list[ChatMessageModel], top_k: int = 10) -> list[ChatMessageModel]:
    if len(objects) <= top_k:
        return objects
    try:
        async with aiohttp.ClientSession() as session:
            result = await (await session.post(
                url="https://api.jina.ai/v1/rerank",
                headers={
                    "Authorization": f"Bearer {config.engine.jina_key}"
                },
                json={
                    "model": "jina-reranker-v2-base-multilingual",
                    "query": query,
                    "top_n": top_k,
                    "documents": [ f"User: {n.query}\n\nAssistant: {n.answer}" for n in objects ],
                    "return_documents": False
                }
            )).json()
            ts = [ objects[i["index"]] for i in result["index"] ]
            return ts
    except Exception:
        return objects[:top_k]

async def embedding(query: str, answer: str = "") -> list[float]:
    if answer == "":
        req = {"model": "jina-embeddings-v3", "task": "retrieval.query", "input": [query]}
    else:
        req = {"model": "jina-embeddings-v3", "task": "retrieval.passage", "input": f"User: {query}\n\nAssistant: {answer}"}
    async with aiohttp.ClientSession() as sess:
        result = await (await sess.post(
            url="https://api.jina.ai/v1/embeddings",
            headers={
                "Authorization": f"Bearer {config.engine.jina_key}"
            },
            json=req
        )).json()
        return result["data"][0]["embedding"]

async def get_conversation(bot: str, target: int, query: str):
    async with vt.orm.Session() as session:
        prpc = (await session.scalar(
            sa.select(sa.func.count())
            .select_from(ChatMessageModel)
        ))
        if prpc is None:
            prpc = 0
        result = [ n._tuple()[0] for n in (await session.execute(
            sa.select(ChatMessageModel)
            .where(ChatMessageModel.bot == bot)
            .where(ChatMessageModel.user == target)
            .order_by(sa.desc(ChatMessageModel.seq))
            .limit(10 if prpc <= 10 else 5)
        )).fetchall() ]
        if prpc > 10:
            result = [ n._tuple()[0] for n in (await session.execute(
                sa.select(ChatMessageModel)
                .where(ChatMessageModel.bot == bot)
                .where(ChatMessageModel.user == target)
                .order_by(ChatMessageModel.vector.cosine_distance(await embedding(query)))
                .limit(10)
            )).fetchall() ]
        result = sorted(await rerank(query, result, top_k=10), key=lambda x: x.seq)
        messages = [{
            "role": "system",
            "content": config.bot[bot].prompt
        }]
        for r in result:
            messages.append({
                "role": "user", "content": r.query
            })
            messages.append({
                "role": "assistant", "content": r.answer
            })
        messages.append({
                "role": "user", "content": query
            })
        return messages

async def tool_userinfo(uid: int):
    try:
        async with aiohttp.ClientSession() as sess:
            result = await (await sess.get(f"https://chat-web-go.jwzhd.com/v1/user/homepage?userId={uid}")).json()
            result = result["data"]["user"]
            if result["userId"] == "":
                raise RuntimeError("icd")
            return json.dumps({ "uid": uid, "nickname": result["nickname"] }, ensure_ascii=False)
    except Exception:
        return "获取用户信息失败！"

async def aichat(bot: str, target: int, query: str):
    record_log({"act": "conversation.start", "query": query}, claimTo=target)
    async with YunhuContext(bot, target) as ctx:
        messages = await get_conversation(bot, target, query)
        assert len(messages) >= 1
        content = ""
        while True:
            try:
                result = (await client.chat.completions.create(
                    model=config.bot[bot].model,
                    messages=messages,
                    tools=[
                        {
                            "type": "builtin_function",
                            "function": {
                                "name": "$web_search",
                            },
                        },
                        {
                            "type": "function",
                            "function": {
                                "name": "userinfo",
                                "description": "获取用户的昵称",
                                "parameters": {"type": "null"}
                            }
                        }
                    ]
                ))
                record_log({"act": "ai.usage", "query": query, "prompt": result.usage.prompt_tokens, "completion": result.usage.completion_tokens}, claimTo=target)
                result = result.choices[0]
                if result.finish_reason == "stop":
                    content += result.message.content
                    ctx.content = content
                    ctx.contentType = "markdown"
                    await ctx.commit()
                    break
                elif result.finish_reason == "length":
                    content += result.message.content
                    if messages[-1].get("partial", False):
                        messages[-1]["content"] = content
                    else:
                        messages.append({
                            "content": content, "role": "assistant", "partial": True
                        })
                elif result.finish_reason == "content_filter":
                    raise openai.ContentFilterFinishReasonError()
                elif result.finish_reason == "tool_calls":
                    messages.append({
                        "content": "",
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": call.id,
                                "type": call.type,
                                "function": {
                                    "name": call.function.name,
                                    "arguments": call.function.arguments
                                }
                            } for call in result.message.tool_calls
                        ]
                    })
                    for call in result.message.tool_calls:
                        record_log({"act": "ai.search", "query": query}, claimTo=target)
                        if call.function.name.startswith("$"):
                            messages.append({
                                "role": "tool",
                                "tool_call_id": call.id,
                                "name": call.function.name,
                                "content": call.function.arguments
                            })
                        elif call.function.name == "userinfo":
                            messages.append({
                                "role": "tool",
                                "tool_call_id": call.id,
                                "name": "userinfo",
                                "content": await tool_userinfo(target)
                            })
                        else:
                            # 404
                            messages.append({
                                "role": "tool",
                                "tool_call_id": call.id,
                                "name": call.function.name,
                                "content": "函数不存在！"
                            })
                else:
                    raise NotImplementedError("Invalid State Transition")
            except openai.RateLimitError:
                ctx.content = "系统繁忙，请稍后再试！"
                ctx.contentType = "text"
                return
            except openai.APITimeoutError:
                ctx.content = "系统繁忙，请稍后再试！"
                ctx.contentType = "text"
                return
            except openai.ContentFilterFinishReasonError:
                record_log({"act": "conversation.violation", "query": query}, claimTo=target)
                ctx.content = "不好意思，我还无法回答这个问题。"
                ctx.contentType = "text"
                return
        record_log({"act": "conversation.commit", "query": query, "answer": content}, claimTo=target)
        async with vt.orm.Session() as sess:
            sess.add(ChatMessageModel(
                bot=bot, user=target, query=query, answer=content, vector=await embedding(query, content)
            ))
            await sess.commit()