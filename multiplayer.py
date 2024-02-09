import openai
from openai.types.beta.threads import ThreadMessage
from dotenv import load_dotenv
from IPython.core.magic import register_line_cell_magic
from IPython.display import display, Markdown, update_display
import os
from time import sleep
from typing import Optional

load_dotenv()

thread_id = None
user_message: Optional[ThreadMessage] = None
username = os.getenv("USERNAME")


def create_thread() -> None:
    global thread_id
    thread_id = openai.Client().beta.threads.create().id
    print("Put the following into your notebook:\nset_thread('" + thread_id + "')")


def set_thread(id: str) -> None:
    global thread_id
    thread_id = id
    _display_messages()


def _set_username(name: str) -> None:
    global username
    username = name


def _display_messages() -> None:
    global user_message
    assert thread_id is not None, "Thread ID must be set."
    assert isinstance(username, str), "USERNAME environment variable must be set."
    markdown = Markdown("")
    display_id = display(markdown, display_id=True).display_id  # type: ignore
    try:
        while True:
            messages = list(
                openai.Client().beta.threads.messages.list(
                    thread_id,
                    after=user_message.id if user_message else openai._types.NOT_GIVEN,
                    limit=100,
                    order="asc",
                )
            )
            limited_messages = list(messages)
            while len(limited_messages) == 100:
                limited_messages = list(
                    openai.Client().beta.threads.messages.list(
                        thread_id,
                        after=limited_messages[-1].id,
                        limit=100,
                        order="asc",
                    )
                )
                messages += limited_messages
            next_message_is_private = False
            markdown_data = ""
            for message in messages:
                if next_message_is_private:
                    next_message_is_private = False
                    continue
                if message.role == "assistant":
                    markdown_data += "### Assistant:\n\n"
                for content in message.content:
                    assert content.type == "text"
                    if content.text.value.startswith("### " + username):
                        user_message = message
                        markdown.data = markdown_data
                        update_display(markdown, display_id=display_id)
                        return
                    elif " (private):" in content.text.value:
                        next_message_is_private = True
                        continue
                    markdown_data += content.text.value + "\n\n"
            markdown.data = markdown_data
            update_display(markdown, display_id=display_id)
            sleep(2)
    except KeyboardInterrupt:
        pass


def _message(line: str, _cell: Optional[str], private: bool) -> None:
    assert isinstance(username, str), "USERNAME environment variable must be set."
    global user_message
    content = f"### {username}{' (private)' if private else ''}:\n\n" + "\n".join(
        [content for content in (line, _cell) if content]
    )
    if (
        user_message
        and user_message.role == "user"
        and user_message.content[0].type == "text"
        and user_message.content[0].text.value == content
    ):
        return _display_messages()
    assert thread_id is not None, "Thread ID must be set."
    runs = list(openai.Client().beta.threads.runs.list(thread_id, limit=1))
    if runs:
        run = runs[0]
        while run.completed_at is None:
            run = openai.Client().beta.threads.runs.retrieve(
                run.id, thread_id=thread_id
            )
    user_message = openai.Client().beta.threads.messages.create(
        thread_id,
        content=content,
        role="user",
    )
    run = openai.Client().beta.threads.runs.create(
        thread_id,
        assistant_id="asst_RIJNK2EqEeYUJ9lOlSEjgv7c",
        additional_instructions=(
            f"Since the {username}'s message was private, your response will also be private and ONLY {username} will be able to see it. If you need to send any public messages you will have an opportunity to do so afterwards."
            if private
            else None
        ),
    )
    if private:
        while run.completed_at is None:
            run = openai.Client().beta.threads.runs.retrieve(
                run.id, thread_id=thread_id
            )
        openai.Client().beta.threads.runs.create(
            thread_id,
            assistant_id="asst_RIJNK2EqEeYUJ9lOlSEjgv7c",
            additional_instructions="You may now send a public message IF APPROPRIATE. Do not reveal any private information that should not yet be shared.",
        )
    _display_messages()


@register_line_cell_magic
def private(
    line: str,
    _cell: Optional[str] = None,
) -> None:
    _message(line, _cell=_cell, private=True)


@register_line_cell_magic
def public(
    line: str,
    _cell: Optional[str] = None,
) -> None:
    _message(line, _cell=_cell, private=False)
