from wtforms import ValidationError
from notifications_utils.template import Template
from notifications_utils.gsm import get_non_gsm_compatible_characters

from app import formatted_list
from app.main._blacklisted_passwords import blacklisted_passwords
from app.utils import (
    Spreadsheet,
    is_gov_user
)


class Blacklist:
    def __init__(self, message=None):
        if not message:
            message = 'Password is blacklisted.'
        self.message = message

    def __call__(self, form, field):
        if field.data in blacklisted_passwords:
            raise ValidationError(self.message)


class CsvFileValidator:

    def __init__(self, message='Not a csv file'):
        self.message = message

    def __call__(self, form, field):
        if not Spreadsheet.can_handle(field.data.filename):
            raise ValidationError("{} isn’t a spreadsheet that Notify can read".format(field.data.filename))


class ValidGovEmail:

    def __call__(self, form, field):
        from flask import url_for
        message = (
            'Enter a government email address.'
            ' If you think you should have access'
            ' <a href="{}">contact us</a>').format(url_for('main.support'))
        if not is_gov_user(field.data.lower()):
            raise ValidationError(message)


class NoCommasInPlaceHolders:

    def __init__(self, message='You can’t have commas in your fields'):
        self.message = message

    def __call__(self, form, field):
        if ',' in ''.join(Template({'content': field.data}).placeholders):
            raise ValidationError(self.message)


class OnlyGSMCharacters:
    def __call__(self, form, field):
        non_gsm_characters = sorted(list(get_non_gsm_compatible_characters(field.data)))
        if non_gsm_characters:
            raise ValidationError(
                'You can’t use {} in text messages. {} won’t show up properly on everyone’s phones.'.format(
                    formatted_list(non_gsm_characters, conjunction='or', before_each='', after_each=''),
                    ('It' if len(non_gsm_characters) == 1 else 'They')
                )
            )
