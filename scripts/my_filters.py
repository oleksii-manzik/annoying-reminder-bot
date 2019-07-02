from telegram.ext import BaseFilter

from .strings import USER_SPECIES, STOP_MESSAGE, START_MESSAGE, CHANGE_DATA_ANSWERS


class UserSpeciesFilter(BaseFilter):
    def filter(self, message):
        return message.text in USER_SPECIES


class TaskFilter(BaseFilter):
    def filter(self, message):
        return message.text not in [*USER_SPECIES, STOP_MESSAGE, START_MESSAGE, *CHANGE_DATA_ANSWERS]


class StopFilter(BaseFilter):
    def filter(self, message):
        return message.text == STOP_MESSAGE


class StartFilter(BaseFilter):
    def filter(self, message):
        return message.text == START_MESSAGE


class ChangeSpecies(BaseFilter):
    def filter(self, message):
        return message.text == CHANGE_DATA_ANSWERS[0]


class ChangeTask(BaseFilter):
    def filter(self, message):
        return message.text == CHANGE_DATA_ANSWERS[1]


class ChangeAll(BaseFilter):
    def filter(self, message):
        return message.text == CHANGE_DATA_ANSWERS[2]


class NotChangingFilter(BaseFilter):
    def filter(self, message):
        return message.text == CHANGE_DATA_ANSWERS[3]
