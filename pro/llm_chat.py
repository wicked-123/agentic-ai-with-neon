"""
Simple chat with gpt-4o-mini using OpenAI API
"""

import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


                                        
def chat(message, system_prompt="You are a helpful assistant.", temperature=0.7):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        temperature=temperature,
    )
    return response.choices[0].message.content


                                                             
def chat_with_history(messages, temperature=0.7):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content


                       
if __name__ == "__main__":
    print("gpt-4o-mini Chat (type 'quit' to exit)\n")

    history = [{"role": "system", "content": "You are a helpful assistant."}]

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("bye!")
            break

        history.append({"role": "user", "content": user_input})

        try:
            reply = chat_with_history(history)
            print(f"Assistant: {reply}\n")
            history.append({"role": "assistant", "content": reply})
        except Exception as e:
            print(f"error: {e}")
