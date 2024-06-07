from openai import OpenAI
import os
from dotenv import load_dotenv
import concurrent.futures


class SafetyChecker:
    def __init__(self):
        load_dotenv()
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    def __call__(self, prompt):
        def make_api_call(content):
            response = self.client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=[{"role": "user", "content": content}],
                temperature=0.0,
                max_tokens=5,
            )
            return response.choices[0].message.content

        content = f'You are a content moderation AI that determines whether user input is appropriate. User input will be used to control a text-to-image generator. For any input that references explicit nudity, sexuality, violence, or gore, reply "unsafe". For copyrighted and tradmarked content (excluding celebrities), reply "copyrighted". For everything else, reply "safe". Evaluate this input: "{prompt}".'

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(make_api_call, content)
            try:
                result = future.result(timeout=5)
            except concurrent.futures.TimeoutError:
                return "safe"

        if "copyrighted" in result:
            return "copyrighted"
        if result == "safe" or result == '"safe"':
            return "safe"
        return "unsafe"
