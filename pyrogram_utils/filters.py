import re
from typing import (
    List,
    Optional,
    Union,
)

import pydash
import pyrogram
from pyrogram import filters

from .callback_data import CallbackData

AnyUpdate = Union[pyrogram.types.Message, pyrogram.types.CallbackQuery, pyrogram.types.InlineQuery]
CallbackOrMessage = Union[pyrogram.types.Message, pyrogram.types.CallbackQuery]


def _check_admin(_, __, update: CallbackOrMessage):
    return pydash.get(update, 'bucket.user.is_admin')


def _check_cq_regex(f, client: pyrogram.Client, cq: pyrogram.types.CallbackQuery):
    return bool(re.match(fr"^({f.data}|{f.data}\?.*)$", cq.data, re.IGNORECASE))


def _check_not_command(f, client: pyrogram.Client, message: pyrogram.types.Message):
    prefixes = list(f.prefixes)
    message_text = message.text or message.caption

    if not message_text:
        return True

    for p in prefixes:
        if message_text.startswith(p):
            return False

    return True


def _check_state(f, client: pyrogram.Client, update: AnyUpdate):
    check_states = f.state if isinstance(f.state, list) else [f.state]

    if '*' in check_states:
        return True

    state = pydash.get(update, 'bucket.user_state.state', None)

    return state in check_states


class CustomFilters:
    admin = filters.create(_check_admin, "AdminRightsFilter")

    @staticmethod
    def callback_data(callback_data: str) -> filters.Filter:
        return filters.create(_check_cq_regex, "CallbackDataRegexFilter", data=callback_data)

    @staticmethod
    def not_command(prefixes: Union[List[str], str] = '/') -> filters.Filter:
        return filters.create(_check_not_command, "CheckNotCommand", prefixes=prefixes)

    @staticmethod
    def state(state: Union[Optional[str], List[Optional[str]]] = '*') -> filters.Filter:
        return filters.create(_check_state, "CheckUserState", state=state)

    @staticmethod
    def reply_command(
            commands: str or list,
            prefixes: str or list = "/",
            case_sensitive: bool = False
    ) -> filters.Filter:
        return filters.incoming & filters.reply & filters.command(commands, prefixes, case_sensitive)

    @staticmethod
    def private_reply_command(
            commands: str or list,
            prefixes: str or list = "/",
            case_sensitive: bool = False
    ) -> filters.Filter:
        return filters.private & CustomFilters.reply_command(commands, prefixes, case_sensitive)

    @staticmethod
    def group_reply_command(
            commands: str or list,
            prefixes: str or list = "/",
            case_sensitive: bool = False
    ) -> filters.Filter:
        return filters.group & CustomFilters.reply_command(commands, prefixes, case_sensitive)


class _BaseFilter(str):
    # Под админом подразумевается проверка прав админа в системе, а не в чате
    __admin: bool = False
    __custom_filter: pyrogram.filters.Filter = None

    def __new__(
            cls,
            value: str,
            *,
            admin: bool = False,
            custom_filter: pyrogram.filters.Filter = None
    ):
        obj = super(_BaseFilter, cls).__new__(cls, value)
        obj.__admin = admin
        obj.__custom_filter = custom_filter

        return obj

    @property
    def filter(self) -> pyrogram.filters.Filter:
        _filter = pyrogram.filters.all

        if self.__admin:
            _filter = CustomFilters.admin & _filter

        if self.__custom_filter is not None:
            _filter = self.__custom_filter & _filter

        return _filter

    def __invert__(self):
        return self.filter.__invert__()

    def __and__(self, other):
        return self.filter.__and__(other)

    def __or__(self, other):
        return self.filter.__or__(other)


class ChatCommand(_BaseFilter):
    __prefix: Union[str, List[str]] = ""
    __private: bool = True

    def __new__(
            cls,
            command: str,
            *,
            prefix: Union[str, List[str]] = "",
            private: bool = True,
            admin: bool = False,
            custom_filter: pyrogram.filters.Filter = None,
    ):
        obj = super(ChatCommand, cls).__new__(
            cls,
            command,
            admin=admin,
            custom_filter=custom_filter
        )
        obj.__prefix = prefix or ""
        obj.__private = private
        return obj

    @property
    def filter(self) -> pyrogram.filters.Filter:
        _filter = super(ChatCommand, self).filter

        if self.__private:
            _filter = pyrogram.filters.private & _filter

        return _filter & pyrogram.filters.command(self, prefixes=self.__prefix)


class SlashCommand(ChatCommand):
    def __new__(
            cls,
            command: str,
            *,
            private: bool = True,
            admin: bool = False,
            custom_filter: pyrogram.filters.Filter = None
    ):
        return super(SlashCommand, cls).__new__(
            cls,
            command,
            prefix='/',
            private=private,
            admin=admin,
            custom_filter=custom_filter
        )


class CallbackAction(_BaseFilter):
    @property
    def filter(self) -> pyrogram.filters.Filter:
        return super(CallbackAction, self).filter & CustomFilters.callback_data(self)

    def pack(self, data: dict = None, **kwargs) -> str:
        data = data or {}
        data.update(**kwargs)
        return CallbackData.pack(self, data)

    def __call__(self, data: dict = None, **kwargs) -> str:
        return self.pack(data, **kwargs)
