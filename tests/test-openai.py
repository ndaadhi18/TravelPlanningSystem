from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os

load_dotenv()

print(os.getenv("OPENAI_API_KEY"))

llm = ChatOpenAI(model_name="gpt-4o-mini")
response = llm.invoke("Hello, how are you?")
print(response.content)