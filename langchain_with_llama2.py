# -*- coding: utf-8 -*-
"""LangChain_with_Llama2.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/137eawajh2IzUOWm6S2QWO7EdDSo81ca-
"""

# !pip -q install git+https://github.com/huggingface/transformers # need to install from github
# !pip install -q datasets loralib sentencepiece
# !pip -q install bitsandbytes accelerate xformers
# !pip -q install langchain
# !pip -q install gradio

# !pip -q install peft chromadb
# !pip -q install unstructured
# !pip install -q sentence_transformers
# !pip -q install pypdf

# !nvidia-smi

from huggingface_hub import login
login(token="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")

import nltk
nltk.download()

"""## LLaMA2 7B Chat

"""

import torch
from peft import PeftModel, PeftConfig
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, pipeline

bnb_config = BitsAndBytesConfig(load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=False)

model_id = "meta-llama/Llama-2-7b-chat-hf"

tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(model_id, quantization_config = bnb_config,device_map={"":0})

# !nvidia-smi

import json
import textwrap

B_INST, E_INST = "[INST]", "[/INST]"
B_SYS, E_SYS = "<<SYS>>\n", "\n<</SYS>>\n\n"
DEFAULT_SYSTEM_PROMPT = """\
You are a helpful, respectful and honest assistant. Always answer as helpfully as possible, while being safe. Your answers should not include any harmful, unethical, racist, sexist, toxic, dangerous, or illegal content. Please ensure that your responses are socially unbiased and positive in nature.

If a question does not make any sense, or is not factually coherent, explain why instead of answering something not correct. If you don't know the answer to a question, please don't share false information."""



def get_prompt(instruction, new_system_prompt=DEFAULT_SYSTEM_PROMPT ):
    SYSTEM_PROMPT = B_SYS + new_system_prompt + E_SYS
    prompt_template =  B_INST + SYSTEM_PROMPT + instruction + E_INST
    return prompt_template

from langchain.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma
from langchain.document_loaders import PyPDFLoader

# loader = PyPDFLoader("/content/World_Chess_Championship_2023.pdf")

loader = PyPDFLoader("address_data_merged.pdf")

text_splitter = RecursiveCharacterTextSplitter(
    # Set a really small chunk size, just to show.
    chunk_size = 500,
    chunk_overlap  = 20,
    length_function = len,
)

pages = loader.load_and_split(text_splitter)

db = Chroma.from_documents(pages, HuggingFaceEmbeddings(), persist_directory = '/content/db')

instruction = "Given the context that has been provided. \n {context}, Answer the following question - \n{question}"

system_prompt = """You are an helpful assistant.
You will be given a context to answer from. Be precise in your answers wherever possible.
In case you are sure you don't know the answer then you say that based on the context you don't know the answer.
In all other instances you provide an answer to the best of your capability. Cite urls when you can access them related to the context."""

get_prompt(instruction, system_prompt)

"""## Setting up with LangChain"""

from langchain import HuggingFacePipeline
from langchain import PromptTemplate,  LLMChain
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory, ConversationBufferWindowMemory

template = get_prompt(instruction, system_prompt)
print(template)

prompt = PromptTemplate(template=template, input_variables=["context", "question"])

memory = ConversationBufferWindowMemory(
    memory_key="chat_history", k=5,
    return_messages=True
)

retriever = db.as_retriever()

def create_pipeline(max_new_tokens=512):
    pipe = pipeline("text-generation",
                model=model,
                tokenizer = tokenizer,
                max_new_tokens = max_new_tokens,
                temperature = 0.5)
    return pipe

class Bot:
  def __init__(self, memory, prompt, task:str = "text-generation", retriever = retriever):
    self.memory = memory
    self.prompt = prompt
    self.retriever = retriever



  def create_chat_bot(self, max_new_tokens = 512):
    hf_pipe = create_pipeline(max_new_tokens)
    llm = HuggingFacePipeline(pipeline =hf_pipe)
    qa = ConversationalRetrievalChain.from_llm(
      llm=llm,
      retriever=self.retriever,
      memory=self.memory,
      combine_docs_chain_kwargs={"prompt": self.prompt}
  )
    return qa

chess_bot = Bot(memory = memory, prompt = prompt)

bot = chess_bot.create_chat_bot()

import gradio as gr
import random
import time

def clear_llm_memory():
  bot.memory.clear()

def update_prompt(sys_prompt):
  if sys_prompt == "":
    sys_prompt = system_prompt
  template = get_prompt(instruction, sys_prompt)

  prompt = PromptTemplate(template=template, input_variables=["context", "question"])

  bot.combine_docs_chain.llm_chain.prompt = prompt

"""1. Not using API
2. Use cases are not defined
3. Just a POC emphasis
"""

with gr.Blocks() as demo:
    update_sys_prompt = gr.Textbox(label = "Update System Prompt")
    chatbot = gr.Chatbot(label="ChatBot", height = 300)
    msg = gr.Textbox(label = "Question")
    clear = gr.ClearButton([msg, chatbot])
    clear_memory = gr.Button(value = "Clear LLM Memory")


    def respond(message, chat_history):
        bot_message = bot({"question": message})['answer']
        chat_history.append((message, bot_message))
        return "", chat_history

    msg.submit(respond, inputs=[msg, chatbot], outputs=[msg, chatbot])
    clear_memory.click(clear_llm_memory)
    update_sys_prompt.submit(update_prompt, inputs=update_sys_prompt)

demo.launch(share=False, debug=True)

