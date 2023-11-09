import os
import re
import json
from typing import List
import openai
from openai import AsyncOpenAI
import uuid
import datetime

import chainlit as cl

from zep_python import (
    MemorySearchPayload,
    ZepClient,
    Memory,
    Message,
    NotFoundError,
    MemorySearchResult,
    Summary,
)


def open_file(filepath):
    with open(filepath, "r", encoding="utf-8") as infile:
        return infile.read()


def save_file(filepath, content):
    with open(filepath, "w", encoding="utf-8") as outfile:
        outfile.write(content)


def log_interaction(user_message: str, prompt: str, response: str):
    now = datetime.datetime.now()
    unique_filename = now.strftime("%Y-%m-%d_%H-%M-%S.json")
    log = {
        "user_message": user_message,
        "prompt": prompt,
        "response": response,
    }
    save_file(f"logs/{unique_filename}", json.dumps(log, indent=4))


def get_base_prompt():
    prompts = [
        "You are an AI co-founder for bootstrapped saas startups.  Your goal is to help single founders or small teams with all the tasks that are required to create a bootstrapped saas. ",
        "You can act as a marketing expert, a sales expert, a software engineer, and a mentor. ",
        "Your goal is to help your human co-founder succeed and support them in any way you can. ",
        "You will be an assistant that can complete tasks for them, remind them of things they might have forgotten, and whatever else your human co-founder needs. ",
        "Be curious about the total project, you want to understand it. ",
        "If you don't understand what your human co-founder is asking, you will ask clarifying questions. ",
        "If you still don't understand, you will say that I don't understand. ",
        "Your answers will be smart and helpful, and you will avoid answering with bulleted or numbered lists of things, unless specifically asked for a list. ",
        "Your name is Al",
    ]
    return [
        {
            "role": "system",
            "content": "\n".join(prompts),
        },
    ]


def get_old_memories(user_input: str, relevancy_threshold=0.75, quantity=10) -> List:
    conversation = []
    ### Get relevant memories via search
    try:
        search_payload = MemorySearchPayload(
            text=str(user_input),
            search_scope="summary",
            search_type="mmr",
            mmr_lambda=0.5,
        )

        relevant_memory: List["MemorySearchResult"] = zep.memory.search_memory(
            session_id, search_payload, quantity
        )
        # Attach a little instruction as to what is going to follow
        conversation.append(
            {
                "role": "system",
                "content": "# Relevant summaries of previous conversation.\n(You do not need to use these pieces of information if not relevant)\n",
            }
        )
        for search_result in relevant_memory:
            print(search_result)
            if search_result.message and search_result.dist > relevancy_threshold:
                conversation.append(
                    {
                        "role": search_result.message.get("role"),
                        "content": search_result.message.get("content"),
                    }
                )
            if search_result.summary:
                s: Summary = search_result.summary
                conversation.append(
                    {
                        "role": "system",
                        "content": f"* {s.content}",
                    }
                )

        # conversation.append(
        #     {
        #         "role": "system",
        #         "content": "(You do not need to use these pieces of information if not relevant)",
        #     }
        # )
    except NotFoundError:
        pass
    ### Get latest memories
    try:
        recent_memory: Memory = zep.memory.get_memory(session_id, quantity)
        {
            "role": "system",
            "content": "# The recent history of this conversation\n",
        }
        if recent_memory.summary:
            conversation.append(
                {
                    "role": "system",
                    "content": f"## SUMMARY OF RECENT CONVERSATIONS\n {recent_memory.summary.content}",
                }
            )
        for message in recent_memory.messages:
            conversation.append(
                {
                    "role": message.role,
                    "content": f"{message.content}",
                }
            )
    except NotFoundError:
        pass
    return conversation


def build_prompt(user_input: str) -> List:
    prompt = get_base_prompt()
    prompt.extend(get_old_memories(user_input))
    prompt.append({"role": "system", "content": "Current conversation: \n"})
    prompt.append({"role": "user", "content": user_input})
    return prompt


def remember_interaction(user_input: str, response: str) -> None:
    new_memory = []
    new_memory.append(Message(role="user", content=user_input))
    new_memory.append(Message(role="assistant", content=response))
    memory = Memory(messages=new_memory)
    zep.memory.add_memory(session_id, memory)


# NOT USED WITH CHAINLIT
#
# def query_chat(prompt: List) -> str:
#     chat_completion = openai.ChatCompletion.create(
#         model="gpt-3.5-turbo",
#         temperature=0.5,
#         messages=prompt,
#     )
#     response_text = chat_completion["choices"][0]["message"]["content"].strip()
#     response_text = re.sub("[\r\n]+", "\n", response_text)
#     response_text = re.sub("[\t ]+", " ", response_text)
#     return response_text


@cl.on_message
async def main(message: cl.Message):
    # if len(message) < 1:
    #     return

    prompt = build_prompt(message.content)

    # response_text = query_chat(prompt)

    msg = cl.Message(
        content="",
    )

    stream = await client.chat.completions.create(
        model="gpt-3.5-turbo",
        temperature=0.5,
        messages=prompt,
        stream=True,
    )
    async for part in stream:
        if token := part.choices[0].delta.content or "":
            await msg.stream_token(token)

    remember_interaction(message.content, msg.content)
    log_interaction(message.content, prompt, msg.content)

    await msg.send()


openai.api_key = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI()
session_id = "2"
zep = ZepClient("http://localhost:8000")
