
import os
from openai import OpenAI

def get_doubao_embedding(text):
    client = OpenAI(
        api_key="7b9dbe35-99a9-42f1-894e-c456063c9a23",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
    )

    resp = client.embeddings.create(
        model="ep-20250208144240-swd8f",
        input=text,
        encoding_format="float"
    )
    return resp.data[0].embedding


class DoubaoEmbedding:
    def __init__(self):
        self.client = OpenAI(
            api_key="7b9dbe35-99a9-42f1-894e-c456063c9a23",
            base_url="https://ark.cn-beijing.volces.com/api/v3",
        )

    def get_embedding(self, text):
        resp = self.client.embeddings.create(
            model="ep-20250208144240-swd8f",
            input=text,
            encoding_format="float"
        )
        return resp.data[0].embedding

