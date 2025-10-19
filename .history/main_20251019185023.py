from playerokapi.account import Account
from playerokapi.types import *
from playerokapi.enums import *
from playerokapi.exceptions import *
from playerokapi.listener.listener import EventListener
import asyncio



TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxZWUxMzg0Ni1lZTQ3LTYxZTAtYmYxOC02OWI2NjAzNTIzNDIiLCJpZGVudGl0eSI6IjFmMDM0ZGViLWEzZTgtNjk1MC00NmFhLTM4NDI3YjU0MzkzMiIsInJvbGUiOiJVU0VSIiwidiI6MSwiaWF0IjoxNzU5MDgyNzYxLCJleHAiOjE3OTA2MTg3NjF9.NYdfpXDDtqz51tkmlOfi5sPQ58dz40KYniCBF1Xk1ns"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
PROXY = None #"FBpmz1:64xwrT@85.195.81.170:10660"



def parse_all_chat_messages(acc: Account, chat_id: str) -> list[ChatMessage]:
    messages = []
    cursor = None
    while True:
        msgs = acc.get_chat_messages(chat_id, after_cursor=cursor)
        if not msgs.messages:
            break
        messages.extend(msgs.messages)
        if not msgs.page_info.end_cursor:
            break
        cursor = msgs.page_info.end_cursor
    return messages



async def main():
    acc = Account(TOKEN, USER_AGENT, proxy=PROXY).get()
    print(acc.get_deals())



if __name__ == "__main__":
    asyncio.run(main())