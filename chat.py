import os
import re
from typing import List
import openai
from dotenv import load_dotenv
from zep_python import (
    MemorySearchPayload,
    ZepClient,
    Memory,
    Message,
    NotFoundError,
    MemorySearchResult,
)

load_dotenv()


def open_file(filepath):
    with open(filepath, "r", encoding="utf-8") as infile:
        return infile.read()


def save_file(filepath, content):
    with open(filepath, "w", encoding="utf-8") as outfile:
        outfile.write(content)


def get_base_prompt():
    return [
        {
            "role": "system",
            "content": "You are an AI co-founder for bootstrapped saas startups.  Your goal is to help single founders or small teams with all the tasks that are required to create a bootstrapped saas.",
        },
        {
            "role": "system",
            "content": "You can act as a marketing expert, a sales expert, a software engineer, and a mentor.",
        },
        {
            "role": "system",
            "content": "Your goal is to help your human co-founder succeed and support them in any way you can.",
        },
        {
            "role": "system",
            "content": "YouI will be an assistant that can complete tasks for them, remind them of things they might have forgotten, and whatever else your human co-founder needs.",
        },
        {
            "role": "system",
            "content": "If you don't understand what your human co-founder is asking, you will ask clarifying questions.",
        },
        {
            "role": "system",
            "content": "If you still don't understand, you will say that I don't understand.",
        },
        {
            "role": "system",
            "content": "Your answers will be smart and helpful, and you will avoid answering with bulleted or numbered lists of things, unless specifically asked for a list.",
        },
        {
            "role": "system",
            "content": "Be curious about the total project, you want to understand it.",
        },
        {
            "role": "system",
            "content": "Your name is Al",
        },
        # {
        #     "role": "system",
        #     "content": "Start response with: |Attribute|Description| |--:|:--| |Domain > Expert|{the broad academic or study DOMAIN the question falls under} > {within the DOMAIN, the specific EXPERT role most closely associated with the context or nuance of the question}| |Keywords|{ CSV list of 6 topics, technical terms, or jargon most associated with the DOMAIN, EXPERT}| |Goal|{ qualitative description of current assistant objective and VERBOSITY }| |Assumptions|{ assistant assumptions about user question, intent, and context}| |Methodology|{any specific methodology assistant will incorporate}|",
        # },
        # {
        #     "role": "system",
        #     "content": "Adopt the role of the EXPERT and return your response, and remember to incorporate: *Assistant Rules and Output Format, *embedded, inline HYPERLINKS as Google search links { varied emoji related to terms} text to link as needed, *step-by-step reasoning if needed",
        # },
    ]


def build_prompt(user_input: str) -> List:
    # prompt = get_base_prompt()
    # prompt.extend(get_old_memories())
    # prompt.append({"role": "user", "content": user_input})
    prompt = get_old_memories()
    prompt.extend(get_base_prompt())
    prompt.append({"role": "user", "content": user_input})
    # print("===================================================")
    # print(prompt)
    # print("===================================================")
    return prompt


def get_old_memories() -> List:
    conversation = []
    ### Get relevant memories via search
    try:
        search_payload = MemorySearchPayload(text=user_input)
        old_memory: List["MemorySearchResult"] = zep.memory.search_memory(
            session_id, search_payload, 20
        )
        for search_result in old_memory:
            conversation.append(
                {
                    "role": search_result.message.get("role"),
                    "content": search_result.message.get("content"),
                }
            )
    except NotFoundError:
        conversation = []
    ### Get latest memories
    try:
        memory: Memory = zep.memory.get_memory(session_id, 10)
        if memory.summary:
            conversation.append(
                {
                    "role": "system",
                    "content": f"SUMMARY OF RECENT CONVERSATIONS\n{memory.summary.content}",
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
        model="gpt-3.5-turbo", messages=prompt
    )
    response_text = chat_completion["choices"][0]["message"]["content"].strip()
    response_text = re.sub("[\r\n]+", "\n", response_text)
    response_text = re.sub("[\t ]+", " ", response_text)
    return response_text


if __name__ == "__main__":
    openai.api_key = os.getenv("OPENAI_API_KEY")
    session_id = "2"
    zep = ZepClient("http://localhost:8000")

    while True:
        user_input = input("\n\nUser: ")

        if len(user_input) < 1:
            continue

        prompt = build_prompt(user_input)
        response_text = query_chat(prompt)
        remember_interaction(user_input, response_text)

        print(response_text)
