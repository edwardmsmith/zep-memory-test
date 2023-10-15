import os
import re
from typing import List
import openai

import chainlit as cl

from zep_python import (
    MemorySearchPayload,
    ZepClient,
    Memory,
    Message,
    NotFoundError,
    MemorySearchResult,
)


def open_file(filepath):
    with open(filepath, "r", encoding="utf-8") as infile:
        return infile.read()


def save_file(filepath, content):
    with open(filepath, "w", encoding="utf-8") as outfile:
        outfile.write(content)


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


def build_prompt(user_input: str) -> List:
    prompt = get_base_prompt()
    prompt.extend(get_old_memories(user_input))
    prompt.append({"role": "system", "content": "Current conversation: \n"})
    prompt.append({"role": "user", "content": user_input})
    # print("===================================================")
    # print(prompt)
    # print("===================================================")
    return prompt


def get_old_memories(user_input: str, relevancy_threshold=0.75, quantity=10) -> List:
    conversation = []
    ### Get relevant memories via search
    try:
        search_payload = MemorySearchPayload(text=user_input)
        relevant_memory: List["MemorySearchResult"] = zep.memory.search_memory(
            session_id, search_payload, quantity
        )
        # Attach a little instruction as to what is going to follow
        conversation.append(
            {
                "role": "system",
                "content": "Relevant pieces of previous conversation: \n",
            }
        )
        for search_result in relevant_memory:
            if search_result.dist > relevancy_threshold:
                conversation.append(
                    {
                        "role": search_result.message.get("role"),
                        "content": search_result.message.get("content"),
                    }
                )
        conversation.append(
            {
                "role": "system",
                "content": "(You do not need to use these pieces of information if not relevant)",
            }
        )
    except NotFoundError:
        conversation = []
    ### Get latest memories
    try:
        recent_memory: Memory = zep.memory.get_memory(session_id, quantity)
        {
            "role": "system",
            "content": "The recent history of this conversation: \n",
        }
        if recent_memory.summary:
            conversation.append(
                {
                    "role": "system",
                    "content": f"SUMMARY OF RECENT CONVERSATIONS\n {recent_memory.summary.content}",
                }
            )
        for message in recent_memory.messages:
            conversation.append(
                {
                    "role": "system",
                    "content": f"{message.content}",
                }
            )
    except NotFoundError:
        pass
    return conversation


def remember_interaction(user_input: str, response: str) -> None:
    new_memory = []
    new_memory.append(Message(role="user", content=user_input))
    new_memory.append(Message(role="assistant", content=response))
    memory = Memory(messages=new_memory)
    zep.memory.add_memory(session_id, memory)


def query_chat(prompt: List) -> str:
    chat_completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        temperature=0.5,
        messages=prompt,
    )
    response_text = chat_completion["choices"][0]["message"]["content"].strip()
    response_text = re.sub("[\r\n]+", "\n", response_text)
    response_text = re.sub("[\t ]+", " ", response_text)
    return response_text


@cl.on_message
async def main(message: str):
    # if len(message) < 1:
    #     return
    prompt = build_prompt(message)

    # response_text = query_chat(prompt)

    msg = cl.Message(
        content="",
    )

    async for stream_resp in await openai.ChatCompletion.acreate(
        model="gpt-3.5-turbo",
        temperature=0.5,
        messages=prompt,
        stream=True,
    ):
        token = stream_resp.choices[0]["delta"].get("content", "")
        await msg.stream_token(token)

    remember_interaction(message, msg.content)

    await msg.send()


openai.api_key = os.getenv("OPENAI_API_KEY")
session_id = "2"
zep = ZepClient("http://localhost:8000")
