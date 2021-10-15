import logging
from functools import partial
from typing import (
    Callable,
    Union,
)

from pyrogram import (
    ContinuePropagation,
    StopPropagation,
)
from pyrogram.middleware import CallNextMiddlewareCallable
from pyrogram.types import (
    CallbackQuery,
    InlineQuery,
    Message,
)

from .filters import _check_admin

log_logger = logging.getLogger('log_middleware')
unhandled_error_logger = logging.getLogger('unhandled_error_middleware')


async def unhandled_error_middleware(
        _,
        update: Union[Message, CallbackQuery],
        call_next: CallNextMiddlewareCallable,
        admin_check: Callable[[Union[Message, CallbackQuery]], bool] = _check_admin
):
    try:
        await call_next(_, update)
    except (ContinuePropagation, StopPropagation):
        raise
    except Exception as e:
        error_text = f'Unhandled exception!\n{e.__class__.__name__}: {e}'

        if not admin_check(update):
            unhandled_error_logger.debug('User is not admin. Skipping displaying an error')
            raise

        if isinstance(update, Message):
            await update.reply(error_text, disable_web_page_preview=True)
        elif isinstance(update, CallbackQuery):
            await update.message.reply(error_text, disable_web_page_preview=True)

        raise


def unhandled_error_middleware_factory(admin_check: Callable[[Union[Message, CallbackQuery]], bool]):
    return partial(unhandled_error_middleware, admin_check=admin_check)


async def log_middleware(_, update: Union[Message, CallbackQuery, InlineQuery], call_next: CallNextMiddlewareCallable):
    logs = []

    if isinstance(update, CallbackQuery):
        logs.append(f"Data: {update.data}")
    elif isinstance(update, InlineQuery):
        logs.append(f"Query: {update.query}")
    elif isinstance(update, Message):
        if bool(update.command):
            logs.append(f"Command: /{' '.join(update.command)}")

        if bool(update.audio):
            logs.append(f"Audio: {update.audio.file_id}")
        elif bool(update.document):
            logs.append(f"Document: {update.document.file_id}")
        elif bool(update.photo):
            logs.append(f"Photo: {update.photo.file_id}")
        elif bool(update.sticker):
            logs.append(f"Sticker: {update.sticker.file_id}")
        elif bool(update.animation):
            logs.append(f"Animation: {update.animation.file_id}")
        elif bool(update.video):
            logs.append(f"Video: {update.video.file_id}")
        elif bool(update.voice):
            logs.append(f"Voice: {update.voice.file_id}")
        elif bool(update.video_note):
            logs.append(f"Video_note: {update.video_note.file_id}")

    user = update.from_user
    user_log = f"User ID: {user.id}"

    if bool(user.username):
        user_log += f" (https://t.me/{user.username})"

    logs.append(user_log)
    log_logger.info(f"[{update.__class__.__name__}] {'; '.join(logs)}")

    return await call_next(_, update)
