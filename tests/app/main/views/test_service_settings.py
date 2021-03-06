import uuid
from unittest.mock import call, ANY, Mock

import pytest
from bs4 import BeautifulSoup
from flask import url_for
from werkzeug.exceptions import InternalServerError

import app
from app.main.views.service_settings import dummy_bearer_token
from app.utils import email_safe
from tests import validate_route_permission, service_json
from tests.conftest import (
    active_user_with_permissions,
    platform_admin_user,
    normalize_spaces,
    no_reply_to_email_addresses,
    multiple_reply_to_email_addresses,
    multiple_letter_contact_blocks,
    no_letter_contact_blocks,
    get_default_reply_to_email_address,
    get_non_default_reply_to_email_address,
    get_default_letter_contact_block,
    get_non_default_letter_contact_block,
    SERVICE_ONE_ID,
)


@pytest.mark.parametrize('user, expected_rows', [
    (active_user_with_permissions, [

        'Label Value Action',
        'Service name service one Change',

        'Label Value Action',
        'Send emails On Change',
        'Email reply to addresses Not set Change',

        'Label Value Action',
        'Send text messages On Change',
        'Text message sender GOVUK Change',
        'International text messages Off Change',
        'Receive text messages Off Change',

        'Label Value Action',
        'Send letters Off Change',

    ]),
    (platform_admin_user, [

        'Label Value Action',
        'Service name service one Change',

        'Label Value Action',
        'Send emails On Change',
        'Email reply to addresses Not set Change',

        'Label Value Action',
        'Send text messages On Change',
        'Text message sender GOVUK Change',
        'International text messages Off Change',
        'Receive text messages Off Change',

        'Label Value Action',
        'Send letters Off Change',

        'Label Value Action',
        'Organisation type Central Change',
        'Free text message allowance 250,000 Change',
        'Email branding GOV.UK Change',
        'Letter branding HM Government Change',

    ]),
])
def test_should_show_overview(
        client,
        mocker,
        service_one,
        fake_uuid,
        mock_get_letter_organisations,
        no_reply_to_email_addresses,
        no_letter_contact_blocks,
        user,
        expected_rows,
        mock_get_inbound_number_for_service
):

    service_one['permissions'] = ['sms', 'email']

    client.login(user(fake_uuid), mocker, service_one)
    response = client.get(url_for(
        'main.service_settings', service_id=service_one['id']
    ))
    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    assert page.find('h1').text == 'Settings'
    rows = page.select('tr')
    assert len(rows) == len(expected_rows)
    for index, row in enumerate(expected_rows):
        assert row == " ".join(rows[index].text.split())
    app.service_api_client.get_service.assert_called_with(service_one['id'])


@pytest.mark.parametrize('permissions, expected_rows', [
    (['email', 'sms', 'inbound_sms', 'international_sms'], [

        'Service name service one Change',

        'Label Value Action',
        'Send emails On Change',
        'Email reply to addresses test@example.com Manage',

        'Label Value Action',
        'Send text messages On Change',
        'Text message sender 0781239871',
        'International text messages On Change',
        'Receive text messages On Change',
        'API endpoint for received text messages Not set Change',

        'Label Value Action',
        'Send letters Off Change',

    ]),
    (['email', 'sms'], [

        'Service name service one Change',

        'Label Value Action',
        'Send emails On Change',
        'Email reply to addresses test@example.com Manage',

        'Label Value Action',
        'Send text messages On Change',
        'Text message sender GOVUK Change',
        'International text messages Off Change',
        'Receive text messages Off Change',

        'Label Value Action',
        'Send letters Off Change',

    ]),
])
def test_should_show_overview_for_service_with_more_things_set(
        client,
        active_user_with_permissions,
        mocker,
        service_one,
        single_reply_to_email_address,
        single_letter_contact_block,
        mock_get_organisation,
        mock_get_letter_organisations,
        mock_get_inbound_number_for_service,
        permissions,
        expected_rows
):
    client.login(active_user_with_permissions, mocker, service_one)
    service_one['permissions'] = permissions
    response = client.get(url_for(
        'main.service_settings', service_id=service_one['id']
    ))
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    for index, row in enumerate(expected_rows):
        assert row == " ".join(page.find_all('tr')[index + 1].text.split())


@pytest.mark.parametrize('url, elided_url', [
    ('https://test.url.com/inbound', 'https://test.url.com...'),
    ('https://test.url.com/', 'https://test.url.com...'),
    ('https://test.url.com', 'https://test.url.com'),
])
def test_service_settings_show_elided_api_url_if_needed(
    logged_in_platform_admin_client,
    service_one,
    mock_get_letter_organisations,
    single_reply_to_email_address,
    single_letter_contact_block,
    mocker,
    fake_uuid,
    url,
    elided_url,
    mock_get_inbound_number_for_service,
):
    service_one['permissions'] = ['sms', 'email', 'inbound_sms']
    service_one['inbound_api'] = [fake_uuid]

    mocked_get_fn = mocker.patch(
        'app.service_api_client.get',
        return_value={'data': {'id': fake_uuid, 'url': url}}
    )

    response = logged_in_platform_admin_client.get(
        url_for(
            'main.service_settings',
            service_id=service_one['id']
        )
    )
    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')

    non_empty_trs = [tr.find_all('td') for tr in page.find_all('tr') if tr.find_all('td')]
    api_url = [api_setting[1].text.strip() for api_setting in non_empty_trs
               if api_setting[0].text.strip() == 'API endpoint for received text messages'][0]
    assert api_url == elided_url
    assert mocked_get_fn.called is True


def test_if_cant_send_letters_then_cant_see_letter_contact_block(
        logged_in_client,
        service_one,
        mock_get_letter_organisations,
        mock_get_inbound_number_for_service
):
    response = logged_in_client.get(url_for(
        'main.service_settings', service_id=service_one['id']
    ))
    assert 'Letter contact block' not in response.get_data(as_text=True)


def test_if_can_receive_inbound_then_cant_change_sms_sender(
        logged_in_client,
        service_one,
        mock_get_letter_organisations,
        single_reply_to_email_address,
        single_letter_contact_block,
        mock_get_inbound_number_for_service
):
    service_one['permissions'] = ['email', 'sms', 'inbound_sms']
    response = logged_in_client.get(url_for(
        'main.service_settings', service_id=service_one['id']
    ))
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    rows_as_text = [" ".join(row.text.split()) for row in page.find_all('tr')]
    assert 'Text message sender 0781239871 Change' not in rows_as_text
    assert url_for('main.service_request_to_go_live', service_id=service_one['id'],
                   set_inbound_sms=False) not in response.get_data(as_text=True)
    assert '0781239871' in response.get_data(as_text=True)


def test_letter_contact_block_shows_none_if_not_set(
        logged_in_client,
        service_one,
        mocker,
        single_reply_to_email_address,
        no_letter_contact_blocks,
        mock_get_letter_organisations,
        mock_get_inbound_number_for_service
):
    service_one['permissions'] = ['letter']
    response = logged_in_client.get(url_for(
        'main.service_settings', service_id=service_one['id']
    ))

    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    div = page.find_all('tr')[8].find_all('td')[1].div
    assert div.text.strip() == 'Not set'
    assert 'default' in div.attrs['class'][0]


def test_escapes_letter_contact_block(
        logged_in_client,
        service_one,
        mocker,
        single_reply_to_email_address,
        injected_letter_contact_block,
        mock_get_letter_organisations,
        mock_get_inbound_number_for_service
):
    service_one['permissions'] = ['letter']
    response = logged_in_client.get(url_for(
        'main.service_settings', service_id=service_one['id']
    ))

    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    div = str(page.find_all('tr')[8].find_all('td')[1].div)
    assert 'foo<br/>bar' in div
    assert '<script>' not in div


def test_should_show_service_name(
        logged_in_client,
        service_one,
):
    response = logged_in_client.get(url_for(
        'main.service_name_change', service_id=service_one['id']))
    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    assert page.find('h1').text == 'Change your service name'
    assert page.find('input', attrs={"type": "text"})['value'] == 'service one'
    app.service_api_client.get_service.assert_called_with(service_one['id'])


def test_should_redirect_after_change_service_name(
        logged_in_client,
        service_one,
        mock_update_service,
        mock_service_name_is_unique
):
    response = logged_in_client.post(
        url_for('main.service_name_change', service_id=service_one['id']),
        data={'name': "new name"})

    assert response.status_code == 302
    settings_url = url_for(
        'main.service_name_change_confirm', service_id=service_one['id'], _external=True)
    assert settings_url == response.location
    assert mock_service_name_is_unique.called


def test_show_restricted_service(
        logged_in_client,
        service_one,
        mock_get_letter_organisations,
        single_reply_to_email_address,
        single_letter_contact_block,
        mock_get_inbound_number_for_service
):
    response = logged_in_client.get(url_for('main.service_settings', service_id=service_one['id']))
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    assert page.find('h1').text == 'Settings'
    assert page.find_all('h2')[0].text == 'Your service is in trial mode'


def test_switch_service_to_live(
        logged_in_platform_admin_client,
        service_one,
        mock_update_service,
        mock_get_inbound_number_for_service
):
    response = logged_in_platform_admin_client.get(
        url_for('main.service_switch_live', service_id=service_one['id']))
    assert response.status_code == 302
    assert response.location == url_for(
        'main.service_settings',
        service_id=service_one['id'], _external=True)
    mock_update_service.assert_called_with(
        service_one['id'],
        message_limit=250000,
        restricted=False
    )


def test_show_live_service(
        logged_in_client,
        service_one,
        mock_get_live_service,
        single_reply_to_email_address,
        single_letter_contact_block,
        mock_get_letter_organisations,
        mock_get_inbound_number_for_service
):
    response = logged_in_client.get(url_for('main.service_settings', service_id=service_one['id']))
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    assert page.find('h1').text.strip() == 'Settings'
    assert 'Your service is in trial mode' not in page.text


def test_switch_service_to_restricted(
        logged_in_platform_admin_client,
        service_one,
        mock_get_live_service,
        mock_update_service,
        mock_get_inbound_number_for_service
):
    response = logged_in_platform_admin_client.get(
        url_for('main.service_switch_live', service_id=service_one['id']))
    assert response.status_code == 302
    assert response.location == url_for(
        'main.service_settings',
        service_id=service_one['id'], _external=True)
    mock_update_service.assert_called_with(
        service_one['id'],
        message_limit=50,
        restricted=True
    )


def test_should_not_allow_duplicate_names(
        logged_in_client,
        mock_service_name_is_not_unique,
        service_one,
):
    service_id = service_one['id']
    response = logged_in_client.post(
        url_for('main.service_name_change', service_id=service_id),
        data={'name': "SErvICE TWO"})

    assert response.status_code == 200
    resp_data = response.get_data(as_text=True)
    assert 'This service name is already in use' in resp_data
    app.service_api_client.is_service_name_unique.assert_called_once_with('SErvICE TWO', 'service.two')


def test_should_show_service_name_confirmation(
        logged_in_client,
        service_one,
):
    response = logged_in_client.get(url_for(
        'main.service_name_change_confirm', service_id=service_one['id']))

    assert response.status_code == 200
    resp_data = response.get_data(as_text=True)
    assert 'Change your service name' in resp_data
    app.service_api_client.get_service.assert_called_with(service_one['id'])


def test_should_redirect_after_service_name_confirmation(
        logged_in_client,
        service_one,
        mock_update_service,
        mock_verify_password,
        mock_get_inbound_number_for_service
):
    service_id = service_one['id']
    service_new_name = 'New Name'
    with logged_in_client.session_transaction() as session:
        session['service_name_change'] = service_new_name
    response = logged_in_client.post(url_for(
        'main.service_name_change_confirm', service_id=service_id))

    assert response.status_code == 302
    settings_url = url_for('main.service_settings', service_id=service_id, _external=True)
    assert settings_url == response.location
    mock_update_service.assert_called_once_with(
        service_id,
        name=service_new_name,
        email_from=email_safe(service_new_name)
    )
    assert mock_verify_password.called


def test_should_raise_duplicate_name_handled(
        logged_in_client,
        service_one,
        mock_update_service_raise_httperror_duplicate_name,
        mock_verify_password
):
    service_new_name = 'New Name'
    with logged_in_client.session_transaction() as session:
        session['service_name_change'] = service_new_name
    response = logged_in_client.post(url_for(
        'main.service_name_change_confirm', service_id=service_one['id']))

    assert response.status_code == 302
    name_change_url = url_for(
        'main.service_name_change', service_id=service_one['id'], _external=True)
    assert name_change_url == response.location
    assert mock_update_service_raise_httperror_duplicate_name.called
    assert mock_verify_password.called


def test_should_show_request_to_go_live(
    client_request,
):
    page = client_request.get(
        'main.service_request_to_go_live', service_id=SERVICE_ONE_ID
    )
    assert page.h1.text == 'Request to go live'
    for channel, label in (
        ('email', 'Emails'),
        ('sms', 'Text messages'),
        ('letter', 'Letters'),
    ):
        assert normalize_spaces(
            page.select_one('label[for=channel_{}]'.format(channel)).text
        ) == label


def test_should_redirect_after_request_to_go_live(
    client_request,
    mocker,
    active_user_with_permissions,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_letter_organisations,
    mock_get_inbound_number_for_service,
):
    mock_post = mocker.patch(
        'app.main.views.feedback.requests.post',
        return_value=Mock(status_code=201),
    )
    page = client_request.post(
        'main.service_request_to_go_live',
        service_id=SERVICE_ONE_ID,
        _data={
            'mou': 'yes',
            'channel_email': 'y',
            'channel_sms': 'y',
            'start_date': '01/01/2017',
            'start_volume': '100,000',
            'peak_volume': '2,000,000',
            'upload_or_api': 'API'
        },
        _follow_redirects=True
    )
    mock_post.assert_called_with(
        ANY,
        data={
            'subject': 'Request to go live - service one',
            'department_id': ANY,
            'agent_team_id': ANY,
            'message': ANY,
            'person_name': active_user_with_permissions.name,
            'person_email': active_user_with_permissions.email_address
        },
        headers=ANY
    )

    returned_message = mock_post.call_args[1]['data']['message']
    assert 'Channel: email and text messages' in returned_message
    assert 'Start date: 01/01/2017' in returned_message
    assert 'Start volume: 100,000' in returned_message
    assert 'Peak volume: 2,000,000' in returned_message
    assert 'Upload or API: API' in returned_message

    assert normalize_spaces(page.select_one('.banner-default').text) == (
        'We’ve received your request to go live'
    )
    assert normalize_spaces(page.select_one('h1').text) == (
        'Settings'
    )


def test_log_error_on_request_to_go_live(
        app_,
        logged_in_client,
        service_one,
        mocker,
):
    mock_post = mocker.patch(
        'app.main.views.service_settings.requests.post',
        return_value=Mock(
            status_code=401,
            json=lambda: {
                'error_code': 'invalid_auth',
                'error_message': 'Please provide a valid API key or token'
            }
        )
    )
    mock_logger = mocker.patch.object(app_.logger, 'error')
    with pytest.raises(InternalServerError):
        logged_in_client.post(
            url_for('main.service_request_to_go_live', service_id=service_one['id']),
            data={
                'mou': 'yes',
                'channel': 'emails',
                'start_date': 'start_date',
                'start_volume': 'start_volume',
                'peak_volume': 'peak_volume',
                'upload_or_api': 'API'
            }
        )
    mock_logger.assert_called_with(
        "Deskpro create ticket request failed with {} '{}'".format(mock_post().status_code, mock_post().json())
    )


@pytest.mark.parametrize('route', [
    'main.service_settings',
    'main.service_name_change',
    'main.service_name_change_confirm',
    'main.service_request_to_go_live',
    'main.archive_service'
])
def test_route_permissions(
        mocker,
        app_,
        client,
        api_user_active,
        service_one,
        single_reply_to_email_address,
        single_letter_contact_block,
        mock_get_letter_organisations,
        route,
        mock_get_inbound_number_for_service
):
    validate_route_permission(
        mocker,
        app_,
        "GET",
        200,
        url_for(route, service_id=service_one['id']),
        ['manage_settings'],
        api_user_active,
        service_one)


@pytest.mark.parametrize('route', [
    'main.service_settings',
    'main.service_name_change',
    'main.service_name_change_confirm',
    'main.service_request_to_go_live',
    'main.service_switch_live',
    'main.service_switch_research_mode',
    'main.service_switch_can_send_letters',
    'main.service_switch_can_send_international_sms',
    'main.archive_service',
])
def test_route_invalid_permissions(
        mocker,
        app_,
        client,
        api_user_active,
        service_one,
        route,
):
    validate_route_permission(
        mocker,
        app_,
        "GET",
        403,
        url_for(route, service_id=service_one['id']),
        ['blah'],
        api_user_active,
        service_one)


@pytest.mark.parametrize('route', [
    'main.service_settings',
    'main.service_name_change',
    'main.service_name_change_confirm',
    'main.service_request_to_go_live',
])
def test_route_for_platform_admin(
        mocker,
        app_,
        client,
        platform_admin_user,
        service_one,
        single_reply_to_email_address,
        single_letter_contact_block,
        mock_get_letter_organisations,
        route,
        mock_get_inbound_number_for_service
):
    validate_route_permission(mocker,
                              app_,
                              "GET",
                              200,
                              url_for(route, service_id=service_one['id']),
                              [],
                              platform_admin_user,
                              service_one)


@pytest.mark.parametrize('route', [
    'main.service_switch_live',
    'main.service_switch_research_mode',
    'main.service_switch_can_send_letters',
    'main.service_switch_can_send_international_sms',
])
def test_route_for_platform_admin_update_service(
        mocker,
        app_,
        client,
        platform_admin_user,
        service_one,
        mock_get_letter_organisations,
        route,
):
    mocker.patch('app.service_api_client.archive_service')
    validate_route_permission(mocker,
                              app_,
                              "GET",
                              302,
                              url_for(route, service_id=service_one['id']),
                              [],
                              platform_admin_user,
                              service_one)


@pytest.mark.parametrize('notification_type, permissions_before_switch, permissions_after_switch', [
    ('email', [], ['email']),
    ('email', ['email'], []),
    ('sms', [], ['sms']),
    ('sms', ['sms'], [])
])
def test_enabling_and_disabling_email_and_sms(
        logged_in_platform_admin_client,
        service_one,
        mocker,
        notification_type,
        permissions_before_switch,
        permissions_after_switch,
        mock_get_inbound_number_for_service
):
    service_one['permissions'] = permissions_before_switch
    mocked_fn = mocker.patch('app.service_api_client.update_service_with_properties', return_value=service_one)

    response = logged_in_platform_admin_client.get(
        url_for('main.service_switch_can_send_{}'.format(notification_type), service_id=service_one['id'])
    )

    assert response.status_code == 302
    assert response.location == url_for('main.service_settings', service_id=service_one['id'], _external=True)
    assert mocked_fn.call_args == call(service_one['id'], {'permissions': permissions_after_switch})


def test_and_more_hint_appears_on_settings_with_more_than_just_a_single_sender(
        client_request,
        service_one,
        mock_get_letter_organisations,
        mock_get_inbound_number_for_service,
        multiple_reply_to_email_addresses,
        multiple_letter_contact_blocks
):
    service_one['permissions'] = ['email', 'sms', 'letter']

    page = client_request.get(
        'main.service_settings',
        service_id=service_one['id']
    )

    assert normalize_spaces(
        page.select('tbody tr')[2].text
    ) == "Email reply to addresses test@example.com …and 2 more Manage"
    assert normalize_spaces(
        page.select('tbody tr')[8].text
    ) == "Sender addresses 1 Example Street …and 2 more Manage"


@pytest.mark.parametrize('sender_list_page, expected_output', [
    ('main.service_email_reply_to', 'test@example.com (default) Change'),
    ('main.service_letter_contact_details', '1 Example Street (default) Change'),
])
def test_api_ids_dont_show_on_option_pages_with_a_single_sender(
    client_request,
    single_reply_to_email_address,
    single_letter_contact_block,
    sender_list_page,
    expected_output
):
    rows = client_request.get(
        sender_list_page,
        service_id=SERVICE_ONE_ID
    ).select(
        '.user-list-item'
    )

    assert normalize_spaces(rows[0].text) == expected_output
    assert len(rows) == 1


@pytest.mark.parametrize(
    'sender_list_page, \
    sample_data, \
    expected_default_sender_output, \
    expected_second_sender_output, \
    expected_third_sender_output',
    [(
        'main.service_email_reply_to',
        multiple_reply_to_email_addresses,
        'test@example.com (default) Change 1234',
        'test2@example.com Change 5678',
        'test3@example.com Change 9457'
    ), (
        'main.service_letter_contact_details',
        multiple_letter_contact_blocks,
        '1 Example Street (default) Change 1234',
        '2 Example Street Change 5678',
        '3 Example Street Change 9457'
    ),
    ]
)
def test_default_option_shows_for_default_sender(
    client_request,
    mocker,
    sender_list_page,
    sample_data,
    expected_default_sender_output,
    expected_second_sender_output,
    expected_third_sender_output
):
    sample_data(mocker)

    rows = client_request.get(
        sender_list_page,
        service_id=SERVICE_ONE_ID
    ).select(
        '.user-list-item'
    )

    assert normalize_spaces(rows[0].text) == expected_default_sender_output
    assert normalize_spaces(rows[1].text) == expected_second_sender_output
    assert normalize_spaces(rows[2].text) == expected_third_sender_output
    assert len(rows) == 3


@pytest.mark.parametrize('sender_list_page, sample_data, expected_output', [
    (
        'main.service_email_reply_to',
        no_reply_to_email_addresses,
        'You haven’t added any email reply to addresses yet'
    ),
    (
        'main.service_letter_contact_details',
        no_letter_contact_blocks,
        'You haven’t added any letter contact details yet'
    ),
])
def test_no_senders_message_shows(
    client_request,
    sender_list_page,
    expected_output,
    sample_data,
    mocker
):
    sample_data(mocker)

    rows = client_request.get(
        sender_list_page,
        service_id=SERVICE_ONE_ID
    ).select(
        '.user-list-item'
    )

    assert normalize_spaces(rows[0].text) == expected_output
    assert len(rows) == 1


@pytest.mark.parametrize('reply_to_input, expected_error', [
    ('', 'Can’t be empty'),
    ('testtest', 'Enter a valid email address'),
    ('test@hello.com', 'Enter a government email address. If you think you should have access contact us')
])
def test_incorrect_reply_to_email_address(
    reply_to_input,
    expected_error,
    client_request,
    no_reply_to_email_addresses
):
    page = client_request.post(
        'main.service_add_email_reply_to',
        service_id=SERVICE_ONE_ID,
        _data={'email_address': reply_to_input},
        _expected_status=200
    )

    assert normalize_spaces(page.select_one('.error-message').text) == expected_error


@pytest.mark.parametrize('contact_block_input, expected_error', [
    ('', 'Can’t be empty'),
    ('1 \n 2 \n 3 \n 4 \n 5 \n 6 \n 7 \n 8 \n 9 \n 0 \n a', 'Contains 11 lines, maximum is 10')
])
def test_incorrect_letter_contact_block(
    contact_block_input,
    expected_error,
    client_request,
    no_letter_contact_blocks
):
    page = client_request.post(
        'main.service_add_letter_contact',
        service_id=SERVICE_ONE_ID,
        _data={'letter_contact_block': contact_block_input},
        _expected_status=200
    )

    assert normalize_spaces(page.select_one('.error-message').text) == expected_error


@pytest.mark.parametrize('fixture, data, api_default_args', [
    (no_reply_to_email_addresses, {}, True),
    (multiple_reply_to_email_addresses, {}, False),
    (multiple_reply_to_email_addresses, {"is_default": "y"}, True)
])
def test_add_reply_to_email_address(
    fixture,
    data,
    api_default_args,
    mocker,
    client_request,
    mock_add_reply_to_email_address
):
    fixture(mocker)
    data['email_address'] = "test@example.gov.uk"
    client_request.post(
        'main.service_add_email_reply_to',
        service_id=SERVICE_ONE_ID,
        _data=data
    )

    mock_add_reply_to_email_address.assert_called_once_with(
        SERVICE_ONE_ID,
        email_address="test@example.gov.uk",
        is_default=api_default_args
    )


@pytest.mark.parametrize('fixture, data, api_default_args', [
    (no_letter_contact_blocks, {}, True),
    (multiple_letter_contact_blocks, {}, False),
    (multiple_letter_contact_blocks, {"is_default": "y"}, True)
])
def test_add_letter_contact(
    fixture,
    data,
    api_default_args,
    mocker,
    client_request,
    mock_add_letter_contact
):
    fixture(mocker)
    data['letter_contact_block'] = "1 Example Street"
    client_request.post(
        'main.service_add_letter_contact',
        service_id=SERVICE_ONE_ID,
        _data=data
    )

    mock_add_letter_contact.assert_called_once_with(
        SERVICE_ONE_ID,
        contact_block="1 Example Street",
        is_default=api_default_args
    )


@pytest.mark.parametrize('sender_page, fixture, checkbox_present', [
    ('main.service_add_email_reply_to', no_reply_to_email_addresses, False),
    ('main.service_add_email_reply_to', multiple_reply_to_email_addresses, True),
    ('main.service_add_letter_contact', no_letter_contact_blocks, False),
    ('main.service_add_letter_contact', multiple_letter_contact_blocks, True)
])
def test_default_box_doesnt_show_on_first_sender(
    sender_page,
    fixture,
    mocker,
    checkbox_present,
    client_request
):
    fixture(mocker)
    page = client_request.get(
        sender_page,
        service_id=SERVICE_ONE_ID
    )

    assert bool(page.select_one('[name=is_default]')) == checkbox_present


@pytest.mark.parametrize('fixture, data, api_default_args', [
    (get_default_reply_to_email_address, {"is_default": "y"}, True),
    (get_default_reply_to_email_address, {}, True),
    (get_non_default_reply_to_email_address, {}, False),
    (get_non_default_reply_to_email_address, {"is_default": "y"}, True)
])
def test_edit_reply_to_email_address(
    fixture,
    data,
    api_default_args,
    mocker,
    fake_uuid,
    client_request,
    mock_update_reply_to_email_address
):
    fixture(mocker)
    data['email_address'] = "test@example.gov.uk"
    client_request.post(
        'main.service_edit_email_reply_to',
        service_id=SERVICE_ONE_ID,
        reply_to_email_id=fake_uuid,
        _data=data
    )

    mock_update_reply_to_email_address.assert_called_once_with(
        SERVICE_ONE_ID,
        reply_to_email_id=fake_uuid,
        email_address="test@example.gov.uk",
        is_default=api_default_args
    )


@pytest.mark.parametrize('fixture, data, api_default_args', [
    (get_default_letter_contact_block, {"is_default": "y"}, True),
    (get_default_letter_contact_block, {}, True),
    (get_non_default_letter_contact_block, {}, False),
    (get_non_default_letter_contact_block, {"is_default": "y"}, True)
])
def test_edit_letter_contact_block(
    fixture,
    data,
    api_default_args,
    mocker,
    fake_uuid,
    client_request,
    mock_update_letter_contact
):
    fixture(mocker)
    data['letter_contact_block'] = "1 Example Street"
    client_request.post(
        'main.service_edit_letter_contact',
        service_id=SERVICE_ONE_ID,
        letter_contact_id=fake_uuid,
        _data=data
    )

    mock_update_letter_contact.assert_called_once_with(
        SERVICE_ONE_ID,
        letter_contact_id=fake_uuid,
        contact_block="1 Example Street",
        is_default=api_default_args
    )


@pytest.mark.parametrize('sender_page, fixture, default_message, params, checkbox_present', [
    (
        'main.service_edit_email_reply_to',
        get_default_reply_to_email_address,
        'This is the default reply to address for service one emails',
        'reply_to_email_id',
        False
    ),
    (
        'main.service_edit_email_reply_to',
        get_non_default_reply_to_email_address,
        'This is the default reply to address for service one emails',
        'reply_to_email_id',
        True
    ),
    (
        'main.service_edit_letter_contact',
        get_default_letter_contact_block,
        'This is currently your default address for service one',
        'letter_contact_id',
        False
    ),
    (
        'main.service_edit_letter_contact',
        get_non_default_letter_contact_block,
        'This is the default contact details for service one letters',
        'letter_contact_id',
        True
    )
])
def test_default_box_shows_on_non_default_sender_details_while_editing(
    fixture,
    fake_uuid,
    mocker,
    sender_page,
    client_request,
    default_message,
    checkbox_present,
    params
):
    page_arguments = {
        'service_id': SERVICE_ONE_ID
    }
    page_arguments[params] = fake_uuid

    fixture(mocker)
    page = client_request.get(
        sender_page,
        **page_arguments
    )

    if checkbox_present:
        assert page.select_one('[name=is_default]')
    else:
        assert normalize_spaces(page.select_one('form p').text) == (
            default_message
        )


def test_switch_service_to_research_mode(
    logged_in_platform_admin_client,
    platform_admin_user,
    service_one,
    mocker,
):
    mocker.patch('app.service_api_client.post', return_value=service_one)
    response = logged_in_platform_admin_client.get(
        url_for('main.service_switch_research_mode', service_id=service_one['id'])
    )
    assert response.status_code == 302
    assert response.location == url_for('main.service_settings', service_id=service_one['id'], _external=True)
    app.service_api_client.post.assert_called_with(
        '/service/{}'.format(service_one['id']),
        {
            'research_mode': True,
            'created_by': platform_admin_user.id
        }
    )


def test_switch_service_from_research_mode_to_normal(
    logged_in_platform_admin_client,
    mocker,
):
    service = service_json(
        research_mode=True
    )
    mocker.patch('app.service_api_client.get_service', return_value={"data": service})
    update_service_mock = mocker.patch('app.service_api_client.update_service_with_properties', return_value=service)

    response = logged_in_platform_admin_client.get(
        url_for('main.service_switch_research_mode', service_id=service['id'])
    )
    assert response.status_code == 302
    assert response.location == url_for('main.service_settings', service_id=service['id'], _external=True)
    update_service_mock.assert_called_with(
        service['id'], {"research_mode": False}
    )


def test_shows_research_mode_indicator(
    logged_in_client,
    service_one,
    mocker,
    mock_get_letter_organisations,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_inbound_number_for_service,
):
    service_one['research_mode'] = True
    mocker.patch('app.service_api_client.update_service_with_properties', return_value=service_one)

    response = logged_in_client.get(url_for('main.service_settings', service_id=service_one['id']))
    assert response.status_code == 200

    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    element = page.find('span', {"id": "research-mode"})
    assert element.text == 'research mode'


def test_does_not_show_research_mode_indicator(
    logged_in_client,
    service_one,
    mock_get_letter_organisations,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_inbound_number_for_service,
):
    response = logged_in_client.get(url_for('main.service_settings', service_id=service_one['id']))
    assert response.status_code == 200

    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    element = page.find('span', {"id": "research-mode"})
    assert not element


@pytest.mark.parametrize('url, bearer_token, expected_errors', [
    ("", "", "Can’t be empty Can’t be empty"),
    ("http://not_https.com", "1234567890", "Must be a valid https url"),
    ("https://test.com", "123456789", "Must be at least 10 characters"),
])
def test_set_inbound_api_validation(
    logged_in_client,
    mock_update_service,
    service_one,
    mock_get_letter_organisations,
    url,
    bearer_token,
    expected_errors,
):
    service_one['permissions'] = ['inbound_sms']
    response = logged_in_client.post(url_for(
        'main.service_set_inbound_api',
        service_id=service_one['id']),
        data={"url": url, "bearer_token": bearer_token}
    )
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    error_msgs = ' '.join(msg.text.strip() for msg in page.select(".error-message"))

    assert response.status_code == 200
    assert error_msgs == expected_errors
    assert not mock_update_service.called


@pytest.mark.parametrize('method', ['get', 'post'])
def test_cant_set_letter_contact_block_if_service_cant_send_letters(
    logged_in_client,
    service_one,
    method,
):
    assert 'letter' not in service_one['permissions']
    response = getattr(logged_in_client, method)(
        url_for('main.service_set_letter_contact_block', service_id=service_one['id'])
    )
    assert response.status_code == 403


def test_set_letter_contact_block_prepopulates(
    logged_in_client,
    service_one,
):
    service_one['permissions'] = ['letter']
    service_one['letter_contact_block'] = 'foo bar baz waz'
    response = logged_in_client.get(url_for('main.service_set_letter_contact_block', service_id=service_one['id']))
    assert response.status_code == 200
    assert 'foo bar baz waz' in response.get_data(as_text=True)


def test_set_letter_contact_block_saves(
    logged_in_client,
    service_one,
    mock_update_service,
):
    service_one['permissions'] = ['letter']
    response = logged_in_client.post(
        url_for('main.service_set_letter_contact_block', service_id=service_one['id']),
        data={'letter_contact_block': 'foo bar baz waz'}
    )
    assert response.status_code == 302
    assert response.location == url_for('main.service_settings', service_id=service_one['id'], _external=True)
    mock_update_service.assert_called_once_with(service_one['id'], letter_contact_block='foo bar baz waz')


def test_set_letter_contact_block_redirects_to_template(
    logged_in_client,
    service_one,
    mock_update_service,
):
    service_one['permissions'] = ['letter']
    fake_template_id = uuid.uuid4()
    response = logged_in_client.post(
        url_for(
            'main.service_set_letter_contact_block',
            service_id=service_one['id'],
            from_template=fake_template_id,
        ),
        data={'letter_contact_block': '23 Whitechapel Road'},
    )
    assert response.status_code == 302
    assert response.location == url_for(
        'main.view_template',
        service_id=service_one['id'],
        template_id=fake_template_id,
        _external=True,
    )


def test_set_letter_contact_block_has_max_10_lines(
    logged_in_client,
    service_one,
    mock_update_service,
):
    service_one['permissions'] = ['letter']
    response = logged_in_client.post(
        url_for('main.service_set_letter_contact_block', service_id=service_one['id']),
        data={'letter_contact_block': '\n'.join(map(str, range(0, 11)))}
    )
    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    error_message = page.find('span', class_='error-message').text.strip()
    assert error_message == 'Contains 11 lines, maximum is 10'


def test_set_letter_branding_platform_admin_only(
    logged_in_client,
    service_one,
):
    response = logged_in_client.get(url_for('main.set_letter_branding', service_id=service_one['id']))
    assert response.status_code == 403


@pytest.mark.parametrize('current_dvla_org_id, expected_selected', [
    (None, '001'),
    ('500', '500'),
])
def test_set_letter_branding_prepopulates(
    logged_in_platform_admin_client,
    service_one,
    mock_get_letter_organisations,
    current_dvla_org_id,
    expected_selected,
):
    if current_dvla_org_id:
        service_one['dvla_organisation'] = current_dvla_org_id
    response = logged_in_platform_admin_client.get(url_for('main.set_letter_branding', service_id=service_one['id']))
    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    assert page.select('input[checked]')[0]['value'] == expected_selected


def test_set_letter_branding_saves(
    logged_in_platform_admin_client,
    service_one,
    mock_update_service,
    mock_get_letter_organisations,
):
    response = logged_in_platform_admin_client.post(
        url_for('main.set_letter_branding', service_id=service_one['id']),
        data={'dvla_org_id': '500'}
    )
    assert response.status_code == 302
    assert response.location == url_for('main.service_settings', service_id=service_one['id'], _external=True)
    mock_update_service.assert_called_once_with(service_one['id'], dvla_organisation='500')


def test_should_show_branding(
    logged_in_platform_admin_client,
    service_one,
    mock_get_organisations,
    mock_get_letter_organisations,
):
    response = logged_in_platform_admin_client.get(url_for(
        'main.service_set_branding_and_org', service_id=service_one['id']
    ))
    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')

    assert page.find('input', attrs={"id": "branding_type-0"})['value'] == 'govuk'
    assert page.find('input', attrs={"id": "branding_type-1"})['value'] == 'both'
    assert page.find('input', attrs={"id": "branding_type-2"})['value'] == 'org'
    assert page.find('input', attrs={"id": "branding_type-3"})['value'] == 'org_banner'

    assert 'checked' in page.find('input', attrs={"id": "branding_type-0"}).attrs
    assert 'checked' not in page.find('input', attrs={"id": "branding_type-1"}).attrs
    assert 'checked' not in page.find('input', attrs={"id": "branding_type-2"}).attrs
    assert 'checked' not in page.find('input', attrs={"id": "branding_type-3"}).attrs

    app.organisations_client.get_organisations.assert_called_once_with()
    app.service_api_client.get_service.assert_called_once_with(service_one['id'])


def test_should_show_organisations(
    logged_in_platform_admin_client,
    service_one,
    mock_get_organisations,
):
    response = logged_in_platform_admin_client.get(url_for(
        'main.service_set_branding_and_org', service_id=service_one['id']
    ))
    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')

    assert page.find('input', attrs={"id": "branding_type-0"})['value'] == 'govuk'
    assert page.find('input', attrs={"id": "branding_type-1"})['value'] == 'both'
    assert page.find('input', attrs={"id": "branding_type-2"})['value'] == 'org'
    assert page.find('input', attrs={"id": "branding_type-3"})['value'] == 'org_banner'

    assert 'checked' in page.find('input', attrs={"id": "branding_type-0"}).attrs
    assert 'checked' not in page.find('input', attrs={"id": "branding_type-1"}).attrs
    assert 'checked' not in page.find('input', attrs={"id": "branding_type-2"}).attrs
    assert 'checked' not in page.find('input', attrs={"id": "branding_type-3"}).attrs

    app.organisations_client.get_organisations.assert_called_once_with()
    app.service_api_client.get_service.assert_called_once_with(service_one['id'])


def test_should_set_branding_and_organisations(
    logged_in_platform_admin_client,
    service_one,
    mock_get_organisations,
    mock_update_service,
):
    response = logged_in_platform_admin_client.post(
        url_for(
            'main.service_set_branding_and_org', service_id=service_one['id']
        ),
        data={
            'branding_type': 'org',
            'organisation': 'organisation-id'
        }
    )
    assert response.status_code == 302
    assert response.location == url_for('main.service_settings', service_id=service_one['id'], _external=True)

    mock_get_organisations.assert_called_once_with()
    mock_update_service.assert_called_once_with(
        service_one['id'],
        branding='org',
        organisation='organisation-id'
    )


@pytest.mark.parametrize('method', ['get', 'post'])
@pytest.mark.parametrize('endpoint', [
    'main.set_organisation_type',
    'main.set_free_sms_allowance',
])
def test_organisation_type_pages_are_platform_admin_only(
    client_request,
    method,
    endpoint,
):
    getattr(client_request, method)(
        endpoint,
        service_id=SERVICE_ONE_ID,
        _expected_status=403,
        _test_page_title=False,
    )


def test_should_show_page_to_set_organisation_type(
    logged_in_platform_admin_client,
):
    response = logged_in_platform_admin_client.get(url_for(
        'main.set_organisation_type',
        service_id=SERVICE_ONE_ID
    ))
    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')

    labels = page.select('label')
    checked_radio_buttons = page.select('input[checked]')

    assert len(checked_radio_buttons) == 1
    assert checked_radio_buttons[0]['value'] == 'central'

    assert len(labels) == 3
    for index, expected in enumerate((
        'Central government',
        'Local government',
        'NHS',
    )):
        assert normalize_spaces(labels[index].text) == expected


@pytest.mark.parametrize('organisation_type', [
    'central',
    'local',
    'nhs',
    pytest.mark.xfail('private sector'),
])
def test_should_set_organisation_type(
    logged_in_platform_admin_client,
    mock_update_service,
    organisation_type,
):
    response = logged_in_platform_admin_client.post(
        url_for(
            'main.set_organisation_type',
            service_id=SERVICE_ONE_ID,
        ),
        data={
            'organisation_type': organisation_type,
            'organisation': 'organisation-id'
        },
    )
    assert response.status_code == 302
    assert response.location == url_for('main.service_settings', service_id=SERVICE_ONE_ID, _external=True)

    mock_update_service.assert_called_once_with(
        SERVICE_ONE_ID,
        organisation_type=organisation_type,
    )


def test_should_show_page_to_set_sms_allowance(
    logged_in_platform_admin_client,
):
    response = logged_in_platform_admin_client.get(url_for(
        'main.set_free_sms_allowance',
        service_id=SERVICE_ONE_ID
    ))
    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')

    assert normalize_spaces(page.select_one('label').text) == 'Numbers of text message fragments per year'


@pytest.mark.parametrize('given_allowance, expected_api_argument', [
    ('1', 1),
    ('250000', 250000),
    pytest.mark.xfail(('foo', 'foo')),
])
def test_should_set_sms_allowance(
    logged_in_platform_admin_client,
    mock_update_service,
    given_allowance,
    expected_api_argument,
):
    response = logged_in_platform_admin_client.post(
        url_for(
            'main.set_free_sms_allowance',
            service_id=SERVICE_ONE_ID,
        ),
        data={
            'free_sms_allowance': given_allowance,
        },
    )
    assert response.status_code == 302
    assert response.location == url_for('main.service_settings', service_id=SERVICE_ONE_ID, _external=True)

    mock_update_service.assert_called_once_with(
        SERVICE_ONE_ID,
        free_sms_fragment_limit=expected_api_argument,
    )


def test_switch_service_enable_letters(
    logged_in_platform_admin_client,
    service_one,
    mocker,
):
    mocked_fn = mocker.patch('app.service_api_client.update_service_with_properties', return_value=service_one)

    response = logged_in_platform_admin_client.get(
        url_for('main.service_switch_can_send_letters', service_id=service_one['id'])
    )

    assert response.status_code == 302
    assert response.location == url_for('main.service_settings', service_id=service_one['id'], _external=True)
    assert 'letter' in mocked_fn.call_args[0][1]['permissions']
    assert mocked_fn.call_args[0][0] == service_one['id']


def test_switch_service_disable_letters(
    logged_in_platform_admin_client,
    service_one,
    mocker,
):
    service_one['permissions'] = ['letter']
    mocked_fn = mocker.patch('app.service_api_client.update_service_with_properties', return_value=service_one)

    response = logged_in_platform_admin_client.get(
        url_for('main.service_switch_can_send_letters', service_id=service_one['id'])
    )

    assert response.status_code == 302
    assert response.location == url_for('main.service_settings', service_id=service_one['id'], _external=True)
    assert mocked_fn.call_args == call(service_one['id'], {"permissions": []})


@pytest.mark.parametrize('permissions, expected_checked', [
    (['international_sms'], 'on'),
    ([''], 'off'),
])
def test_show_international_sms_as_radio_button(
    client_request,
    service_one,
    mocker,
    permissions,
    expected_checked,
):
    service_one['permissions'] = permissions

    checked_radios = client_request.get(
        'main.service_set_international_sms',
        service_id=service_one['id'],
    ).select(
        '.multiple-choice input[checked]'
    )

    assert len(checked_radios) == 1
    assert checked_radios[0]['value'] == expected_checked


@pytest.mark.parametrize('post_value, international_sms_permission_expected_in_api_call', [
    ('on', True),
    ('off', False),
])
def test_switch_service_enable_international_sms(
    client_request,
    service_one,
    mocker,
    post_value,
    international_sms_permission_expected_in_api_call,
):
    mocked_fn = mocker.patch('app.service_api_client.update_service_with_properties', return_value=service_one)
    client_request.post(
        'main.service_set_international_sms',
        service_id=service_one['id'],
        _data={
            'enabled': post_value
        },
        _expected_redirect=url_for('main.service_settings', service_id=service_one['id'], _external=True)
    )

    if international_sms_permission_expected_in_api_call:
        assert 'international_sms' in mocked_fn.call_args[0][1]['permissions']
    else:
        assert 'international_sms' not in mocked_fn.call_args[0][1]['permissions']

    assert mocked_fn.call_args[0][0] == service_one['id']


def test_set_new_inbound_api_and_valid_bearer_token_calls_create_inbound_api_endpoint(
    logged_in_platform_admin_client,
    service_one,
    mocker,
):
    service_one['permissions'] = ['inbound_sms']
    service_one['inbound_api'] = []

    mocked_post_fn = mocker.patch('app.service_api_client.post', return_value=service_one)

    inbound_api_data = {'url': "https://test.url.com/", 'bearer_token': '1234567890'}
    response = logged_in_platform_admin_client.post(
        url_for(
            'main.service_set_inbound_api',
            service_id=service_one['id']
        ),
        data=inbound_api_data
    )
    assert response.status_code == 302
    assert response.location == url_for('main.service_settings', service_id=service_one['id'], _external=True)
    assert mocked_post_fn.called

    inbound_api_data['updated_by_id'] = service_one['users'][0]
    assert mocked_post_fn.call_args == call("/service/{}/inbound-api".format(service_one['id']), inbound_api_data)


@pytest.mark.parametrize(
    'inbound_api_data', [
        {'url': "https://test.url.com/inbound", 'bearer_token': dummy_bearer_token},
        {'url': "https://test.url.com/inbound", 'bearer_token': '1234567890'},
        {'url': "https://test.url.com/", 'bearer_token': 'new_1234567890'},
    ]
)
def test_update_inbound_api_and_valid_bearer_token_calls_update_inbound_api_endpoint(
    logged_in_platform_admin_client,
    service_one,
    mocker,
    fake_uuid,
    inbound_api_data,
):
    service_one['permissions'] = ['inbound_sms']
    service_one['inbound_api'] = [fake_uuid]

    initial_api_data = {'data': {'id': fake_uuid, 'url': "https://test.url.com/"}}

    mocked_get_fn = mocker.patch('app.service_api_client.get', return_value=initial_api_data)
    mocked_post_fn = mocker.patch('app.service_api_client.post', return_value=service_one)

    response = logged_in_platform_admin_client.get(
        url_for(
            'main.service_set_inbound_api',
            service_id=service_one['id']
        )
    )
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')

    assert page.find('input', {'id': 'url'}).get('value') == initial_api_data['data']['url']
    assert page.find('input', {'id': 'bearer_token'}).get('value') == dummy_bearer_token

    response = logged_in_platform_admin_client.post(
        url_for(
            'main.service_set_inbound_api',
            service_id=service_one['id']
        ),
        data=inbound_api_data
    )
    assert response.status_code == 302
    assert response.location == url_for('main.service_settings', service_id=service_one['id'], _external=True)
    assert mocked_get_fn.called is True
    assert mocked_post_fn.called is True

    if inbound_api_data['bearer_token'] == dummy_bearer_token:
        del inbound_api_data['bearer_token']
    inbound_api_data['updated_by_id'] = service_one['users'][0]

    assert mocked_post_fn.call_args == call(
        "/service/{}/inbound-api/{}".format(service_one['id'], fake_uuid), inbound_api_data)


def test_save_inbound_api_without_changes_does_not_update_inbound_api(
    logged_in_platform_admin_client,
    service_one,
    mocker,
    fake_uuid,
):
    service_one['permissions'] = ['inbound_sms']
    service_one['inbound_api'] = [fake_uuid]

    initial_api_data = {'data': {'id': fake_uuid, 'url': "https://test.url.com/"}}
    inbound_api_data = {'url': initial_api_data['data']['url'], 'bearer_token': dummy_bearer_token}

    mocked_get_fn = mocker.patch('app.service_api_client.get', return_value=initial_api_data)
    mocked_post_fn = mocker.patch('app.service_api_client.post', return_value=service_one)

    response = logged_in_platform_admin_client.post(
        url_for(
            'main.service_set_inbound_api',
            service_id=service_one['id']
        ),
        data=inbound_api_data
    )
    assert response.status_code == 302
    assert response.location == url_for('main.service_settings', service_id=service_one['id'], _external=True)
    assert mocked_get_fn.called is True
    assert mocked_post_fn.called is False


def test_archive_service_after_confirm(
    logged_in_platform_admin_client,
    service_one,
    mocker,
    mock_get_inbound_number_for_service,
):
    mocked_fn = mocker.patch('app.service_api_client.post', return_value=service_one)

    response = logged_in_platform_admin_client.post(url_for('main.archive_service', service_id=service_one['id']))

    assert response.status_code == 302
    assert response.location == url_for('main.service_settings', service_id=service_one['id'], _external=True)
    assert mocked_fn.call_args == call('/service/{}/archive'.format(service_one['id']), data=None)


def test_archive_service_prompts_user(
    logged_in_platform_admin_client,
    service_one,
    mocker,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_letter_organisations,
    mock_get_inbound_number_for_service,
):
    mocked_fn = mocker.patch('app.service_api_client.post')

    response = logged_in_platform_admin_client.get(url_for('main.archive_service', service_id=service_one['id']))

    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    assert 'Are you sure you want to archive this service?' in page.find('div', class_='banner-dangerous').text
    assert mocked_fn.called is False


def test_cant_archive_inactive_service(
    logged_in_platform_admin_client,
    service_one,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_letter_organisations,
    mock_get_inbound_number_for_service,
):
    service_one['active'] = False

    response = logged_in_platform_admin_client.get(url_for('main.service_settings', service_id=service_one['id']))

    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    assert 'Archive service' not in {a.text for a in page.find_all('a', class_='button')}


def test_suspend_service_after_confirm(
    logged_in_platform_admin_client,
    service_one,
    mocker,
    mock_get_inbound_number_for_service,
):
    mocked_fn = mocker.patch('app.service_api_client.post', return_value=service_one)

    response = logged_in_platform_admin_client.post(url_for('main.suspend_service', service_id=service_one['id']))

    assert response.status_code == 302
    assert response.location == url_for('main.service_settings', service_id=service_one['id'], _external=True)
    assert mocked_fn.call_args == call('/service/{}/suspend'.format(service_one['id']), data=None)


def test_suspend_service_prompts_user(
    logged_in_platform_admin_client,
    service_one,
    mocker,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_letter_organisations,
    mock_get_inbound_number_for_service,
):
    mocked_fn = mocker.patch('app.service_api_client.post')

    response = logged_in_platform_admin_client.get(url_for('main.suspend_service', service_id=service_one['id']))

    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    assert 'This will suspend the service and revoke all api keys. Are you sure you want to suspend this service?' in \
           page.find('div', class_='banner-dangerous').text
    assert mocked_fn.called is False


def test_cant_suspend_inactive_service(
    logged_in_platform_admin_client,
    service_one,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_letter_organisations,
    mock_get_inbound_number_for_service,
):
    service_one['active'] = False

    response = logged_in_platform_admin_client.get(url_for('main.service_settings', service_id=service_one['id']))

    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    assert 'Suspend service' not in {a.text for a in page.find_all('a', class_='button')}


def test_resume_service_after_confirm(
    logged_in_platform_admin_client,
    service_one,
    single_reply_to_email_address,
    single_letter_contact_block,
    mocker,
    mock_get_inbound_number_for_service,
):
    service_one['active'] = False
    mocked_fn = mocker.patch('app.service_api_client.post', return_value=service_one)

    response = logged_in_platform_admin_client.post(url_for('main.resume_service', service_id=service_one['id']))

    assert response.status_code == 302
    assert response.location == url_for('main.service_settings', service_id=service_one['id'], _external=True)
    assert mocked_fn.call_args == call('/service/{}/resume'.format(service_one['id']), data=None)


def test_resume_service_prompts_user(
    logged_in_platform_admin_client,
    service_one,
    single_reply_to_email_address,
    single_letter_contact_block,
    mocker,
    mock_get_letter_organisations,
    mock_get_inbound_number_for_service,
):
    service_one['active'] = False
    mocked_fn = mocker.patch('app.service_api_client.post')

    response = logged_in_platform_admin_client.get(url_for('main.resume_service', service_id=service_one['id']))

    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    assert 'This will resume the service. New api key are required for this service to use the API.' in \
           page.find('div', class_='banner-dangerous').text
    assert mocked_fn.called is False


def test_cant_resume_active_service(
    logged_in_platform_admin_client,
    service_one,
    single_reply_to_email_address,
    single_letter_contact_block,
    mock_get_letter_organisations,
    mock_get_inbound_number_for_service,
):
    response = logged_in_platform_admin_client.get(url_for('main.service_settings', service_id=service_one['id']))

    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    assert 'Resume service' not in {a.text for a in page.find_all('a', class_='button')}


@pytest.mark.parametrize('endpoint, permissions, expected_p', [
    (
        'main.service_set_letters',
        [],
        (
            'Using GOV.UK Notify to send letters is an invitation‑only '
            'feature.'
        )
    ),
    (
        'main.service_set_letters',
        ['letter'],
        (
            'Your service can send letters.'
        )
    ),
    (
        'main.service_set_inbound_sms',
        ['sms'],
        (
            'Receiving text messages from your users is an invitation‑only feature.'
        )
    ),
    (
        'main.service_set_inbound_sms',
        ['sms', 'inbound_sms'],
        (
            'Your service can receive text messages sent to 0781239871.'
        )
    ),
])
def test_invitation_pages(
    logged_in_client,
    service_one,
    mock_get_inbound_number_for_service,
    endpoint,
    permissions,
    expected_p,
):
    service_one['permissions'] = permissions
    response = logged_in_client.get(url_for(endpoint, service_id=service_one['id']))

    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    assert normalize_spaces(page.select('main p')[0].text) == expected_p


def test_service_settings_when_inbound_number_is_not_set(
    logged_in_client,
    service_one,
    single_reply_to_email_address,
    single_letter_contact_block,
    mocker,
    mock_get_letter_organisations,
):
    mocker.patch('app.inbound_number_client.get_inbound_sms_number_for_service',
                 return_value={'data': {}})
    response = logged_in_client.get(url_for(
        'main.service_settings', service_id=service_one['id']
    ))
    assert response.status_code == 200


def test_set_inbound_sms_when_inbound_number_is_not_set(
    logged_in_client,
    service_one,
    single_reply_to_email_address,
    single_letter_contact_block,
    mocker,
    mock_get_letter_organisations,
):
    mocker.patch('app.inbound_number_client.get_inbound_sms_number_for_service',
                 return_value={'data': {}})
    response = logged_in_client.get(url_for(
        'main.service_set_inbound_sms', service_id=service_one['id']
    ))
    assert response.status_code == 200


def test_empty_letter_contact_block_returns_error(
    logged_in_client,
    service_one,
    mock_update_service,
):
    service_one['permissions'] = ['letter']
    response = logged_in_client.post(
        url_for('main.service_set_letter_contact_block', service_id=service_one['id']),
        data={'letter_contact_block': None}
    )

    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    error_message = page.find('span', class_='error-message').text.strip()
    assert error_message == 'Can’t be empty'
