from bs4 import BeautifulSoup, element
from functools import partial
import pytest
from flask import url_for
from werkzeug.exceptions import InternalServerError
from unittest.mock import Mock, ANY
from freezegun import freeze_time
from tests.conftest import (
    mock_get_services,
    mock_get_services_with_no_services,
    mock_get_services_with_one_service
)
from app.main.views.feedback import has_live_services, in_business_hours


def no_redirect():
    return lambda _external=True: None


@pytest.mark.parametrize('endpoint', [
    'main.old_feedback',
    'main.support',
])
def test_get_support_index_page(
    client,
    endpoint,
):
    response = client.get(url_for('main.support'), follow_redirects=True)
    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    assert page.h1.string.strip() == 'Support'


@freeze_time('2016-12-12 12:00:00.000000')
@pytest.mark.parametrize('support_type, expected_h1', [
    ('problem', 'Report a problem'),
    ('question', 'Ask a question or give feedback'),
])
@pytest.mark.parametrize('logged_in, expected_form_field, expected_contact_details', [
    (True, type(None), 'We’ll reply to test@user.gov.uk'),
    (False, element.Tag, None),
])
def test_choose_support_type(
    client,
    api_user_active,
    mock_get_user,
    mock_get_services,
    logged_in,
    expected_form_field,
    expected_contact_details,
    support_type,
    expected_h1
):
    if logged_in:
        client.login(api_user_active)
    response = client.post(
        url_for('main.support'),
        data={'support_type': support_type}, follow_redirects=True
    )
    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    assert page.h1.string.strip() == expected_h1
    assert isinstance(page.find('input', {'name': 'name'}), expected_form_field)
    assert isinstance(page.find('input', {'name': 'email_address'}), expected_form_field)
    if expected_contact_details:
        assert page.find('form').find('p').text.strip() == expected_contact_details


@freeze_time('2016-12-12 12:00:00.000000')
@pytest.mark.parametrize('ticket_type, expected_status_code', [
    ('problem', 200),
    ('question', 200),
    ('gripe', 404)
])
def test_get_feedback_page(client, ticket_type, expected_status_code):
    response = client.get(url_for('main.feedback', ticket_type=ticket_type))
    assert response.status_code == expected_status_code


@freeze_time('2016-12-12 12:00:00.000000')
@pytest.mark.parametrize('ticket_type', ['problem', 'question'])
def test_passed_non_logged_in_user_details_through_flow(client, mocker, ticket_type):
    mock_post = mocker.patch(
        'app.main.views.feedback.requests.post',
        return_value=Mock(status_code=201)
    )

    data = {'feedback': 'blah', 'name': 'Steve Irwin', 'email_address': 'rip@gmail.com'}

    resp = client.post(
        url_for('main.feedback', ticket_type=ticket_type),
        data=data
    )

    assert resp.status_code == 302
    assert resp.location == url_for('main.thanks', urgent=True, anonymous=False, _external=True)
    mock_post.assert_called_with(
        ANY,
        data={
            'department_id': ANY,
            'agent_team_id': ANY,
            'subject': 'Notify feedback {}'.format(data['name']),
            'message': 'Environment: http://localhost/\n\nblah',
            'person_email': 'rip@gmail.com',
            'person_name': 'Steve Irwin',
            'label': ticket_type,
            'urgency': ANY,
        },
        headers=ANY
    )


@freeze_time("2016-12-12 12:00:00.000000")
@pytest.mark.parametrize('data', [
    {'feedback': 'blah'},
    {'feedback': 'blah', 'name': 'Ignored', 'email_address': 'ignored@email.com'}
])
@pytest.mark.parametrize('ticket_type', ['problem', 'question'])
def test_passes_user_details_through_flow(
    logged_in_client,
    mocker,
    ticket_type,
    data
):
    mock_post = mocker.patch(
        'app.main.views.feedback.requests.post',
        return_value=Mock(status_code=201)
    )

    resp = logged_in_client.post(
        url_for('main.feedback', ticket_type=ticket_type),
        data=data,
    )

    assert resp.status_code == 302
    assert resp.location == url_for('main.thanks', urgent=True, anonymous=False, _external=True)
    mock_post.assert_called_with(
        ANY,
        data={
            'department_id': ANY,
            'agent_team_id': ANY,
            'subject': 'Notify feedback Test User',
            'message': ANY,
            'person_email': 'test@user.gov.uk',
            'person_name': 'Test User',
            'label': ticket_type,
            'urgency': ANY,
        },
        headers=ANY
    )
    assert mock_post.call_args[1]['data']['message'] == '\n'.join([
        'Environment: http://localhost/',
        'Service "service one": {}'.format(url_for(
            'main.service_dashboard',
            service_id='596364a0-858e-42c8-9062-a8fe822260eb',
            _external=True
        )),
        '',
        'blah',
    ])


@freeze_time('2016-12-12 12:00:00.000000')
@pytest.mark.parametrize('data', [
    {'feedback': 'blah', 'name': 'Fred'},
    {'feedback': 'blah'},
])
@pytest.mark.parametrize('ticket_type, expected_response, things_expected_in_url, expected_error', [
    ('problem', 200, [], element.Tag),
    ('question', 302, ['thanks', 'anonymous=True', 'urgent=True'], type(None)),
])
def test_email_address_required_for_problems(
    client,
    mocker,
    data,
    ticket_type,
    expected_response,
    things_expected_in_url,
    expected_error
):
    mocker.patch(
        'app.main.views.feedback.requests.post',
        return_value=Mock(status_code=201)
    )
    response = client.post(
        url_for('main.feedback', ticket_type=ticket_type),
        data=data,
    )
    assert response.status_code == expected_response
    # This is to work around non-deterministic query ordering in Flask url_for
    for thing in things_expected_in_url:
        assert thing in response.location
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    assert isinstance(page.find('span', {'class': 'error-message'}), expected_error)


@pytest.mark.parametrize('ticket_type, severe, is_in_business_hours, numeric_urgency, is_urgent', [

    # business hours, always urgent
    ('problem', 'yes', True, 10, True),
    ('question', 'yes', True, 10, True),
    ('problem', 'no', True, 10, True),
    ('question', 'no', True, 10, True),

    # out of hours, non emergency, never urgent
    ('problem', 'no', False, 1, False),
    ('question', 'no', False, 1, False),

    # out of hours, emergency problems are urgent
    ('problem', 'yes', False, 10, True),
    ('question', 'yes', False, 1, False),

])
def test_urgency(
    logged_in_client,
    mocker,
    ticket_type,
    severe,
    is_in_business_hours,
    numeric_urgency,
    is_urgent,
):
    mocker.patch('app.main.views.feedback.in_business_hours', return_value=is_in_business_hours)
    mock_post = mocker.patch('app.main.views.feedback.requests.post', return_value=Mock(status_code=201))
    response = logged_in_client.post(
        url_for('main.feedback', ticket_type=ticket_type, severe=severe),
        data={'feedback': 'blah', 'email_address': 'test@example.com'},
    )
    assert response.status_code == 302
    assert response.location == url_for('main.thanks', urgent=is_urgent, anonymous=False, _external=True)
    assert mock_post.call_args[1]['data']['urgency'] == numeric_urgency


ids, params = zip(*[
    ('non-logged in users always have to triage', (
        'problem', False, False, True,
        302, partial(url_for, 'main.triage')
    )),
    ('trial services are never high priority', (
        'problem', False, True, False,
        200, no_redirect()
    )),
    ('we can triage in hours', (
        'problem', True, True, True,
        200, no_redirect()
    )),
    ('only problems are high priority', (
        'question', False, True, True,
        200, no_redirect()
    )),
    ('should triage out of hours', (
        'problem', False, True, True,
        302, partial(url_for, 'main.triage')
    ))
])


@pytest.mark.parametrize(
    (
        'ticket_type, is_in_business_hours, logged_in, has_live_services,'
        'expected_status, expected_redirect'
    ),
    params, ids=ids
)
def test_redirects_to_triage(
    client,
    api_user_active,
    mocker,
    mock_get_user,
    ticket_type,
    is_in_business_hours,
    logged_in,
    has_live_services,
    expected_status,
    expected_redirect,
):
    mocker.patch('app.main.views.feedback.has_live_services', return_value=has_live_services)
    mocker.patch('app.main.views.feedback.in_business_hours', return_value=is_in_business_hours)
    if logged_in:
        client.login(api_user_active)

    response = client.get(url_for('main.feedback', ticket_type=ticket_type))
    assert response.status_code == expected_status
    assert response.location == expected_redirect(_external=True)


def test_doesnt_lose_message_if_post_across_closing(
    logged_in_client,
    mocker,
):

    mocker.patch('app.main.views.feedback.has_live_services', return_value=True)
    mocker.patch('app.main.views.feedback.in_business_hours', return_value=False)

    response = logged_in_client.post(
        url_for('main.feedback', ticket_type='problem'),
        data={'feedback': 'foo'},
    )
    with logged_in_client.session_transaction() as session:
        assert session['feedback_message'] == 'foo'
    assert response.status_code == 302
    assert response.location == url_for('.triage', _external=True)

    response = logged_in_client.get(
        url_for('main.feedback', ticket_type='problem', severe='yes')
    )
    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    with logged_in_client.session_transaction() as session:
        assert page.find('textarea', {'name': 'feedback'}).text == 'foo'
        assert 'feedback_message' not in session


@pytest.mark.parametrize('get_services_mock, expected_return_value', [
    (mock_get_services, True),
    (mock_get_services_with_no_services, False),
    (mock_get_services_with_one_service, False),
])
def test_has_live_services(
    mocker,
    fake_uuid,
    get_services_mock,
    expected_return_value
):
    get_services_mock(mocker, fake_uuid)
    assert has_live_services(12345) == expected_return_value


@pytest.mark.parametrize('when, is_in_business_hours', [

    ('2016-06-06 09:29:59+0100', False),  # opening time, summer and winter
    ('2016-12-12 09:29:59+0000', False),
    ('2016-06-06 09:30:00+0100', True),
    ('2016-12-12 09:30:00+0000', True),

    ('2016-12-12 12:00:00+0000', True),   # middle of the day

    ('2016-12-12 17:29:59+0000', True),   # closing time
    ('2016-12-12 17:30:00+0000', False),

    ('2016-12-10 12:00:00+0000', False),  # Saturday
    ('2016-12-11 12:00:00+0000', False),  # Sunday
    ('2016-01-01 12:00:00+0000', False),  # Bank holiday

])
def test_in_business_hours(when, is_in_business_hours):
    with freeze_time(when):
        assert in_business_hours() == is_in_business_hours


@pytest.mark.parametrize('choice, expected_redirect_param', [
    ('yes', 'yes'),
    ('no', 'no'),
])
def test_triage_redirects_to_correct_url(client, choice, expected_redirect_param):
    response = client.post(url_for('main.triage'), data={'severe': choice})
    assert response.status_code == 302
    assert response.location == url_for(
        'main.feedback',
        ticket_type='problem',
        severe=expected_redirect_param,
        _external=True,
    )


@pytest.mark.parametrize(
    (
        'is_in_business_hours, severe,'
        'expected_status_code, expected_redirect,'
        'expected_status_code_when_logged_in, expected_redirect_when_logged_in'
    ),
    [
        (
            True, 'yes',
            200, no_redirect(),
            200, no_redirect()
        ),
        (
            True, 'no',
            200, no_redirect(),
            200, no_redirect()
        ),
        (
            False, 'no',
            200, no_redirect(),
            200, no_redirect(),
        ),

        # Treat empty query param as mangled URL – ask question again
        (
            False, '',
            302, partial(url_for, 'main.triage'),
            302, partial(url_for, 'main.triage'),
        ),

        # User hasn’t answered the triage question
        (
            False, None,
            302, partial(url_for, 'main.triage'),
            302, partial(url_for, 'main.triage'),
        ),

        # Escalation is needed for non-logged-in users
        (
            False, 'yes',
            302, partial(url_for, 'main.bat_phone'),
            200, no_redirect(),
        ),
    ]
)
def test_should_be_shown_the_bat_email(
    client,
    active_user_with_permissions,
    mocker,
    service_one,
    mock_get_services,
    is_in_business_hours,
    severe,
    expected_status_code,
    expected_redirect,
    expected_status_code_when_logged_in,
    expected_redirect_when_logged_in,
):

    mocker.patch('app.main.views.feedback.in_business_hours', return_value=is_in_business_hours)

    feedback_page = url_for('main.feedback', ticket_type='problem', severe=severe)

    response = client.get(feedback_page)

    assert response.status_code == expected_status_code
    assert response.location == expected_redirect(_external=True)

    # logged in users should never be redirected to the bat email page
    client.login(active_user_with_permissions, mocker, service_one)
    logged_in_response = client.get(feedback_page)
    assert logged_in_response.status_code == expected_status_code_when_logged_in
    assert logged_in_response.location == expected_redirect_when_logged_in(_external=True)


def test_bat_email_page(
    client,
    active_user_with_permissions,
    mocker,
    service_one,
):
    bat_phone_page = url_for('main.bat_phone')

    response = client.get(bat_phone_page)
    assert response.status_code == 200

    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    assert page.select('main a')[1].text == 'Fill in this form'
    assert page.select('main a')[1]['href'] == url_for('main.feedback', ticket_type='problem', severe='no')
    next_page_response = client.get(page.select('main a')[1]['href'])
    next_page = BeautifulSoup(next_page_response.data.decode('utf-8'), 'html.parser')
    assert next_page.h1.text.strip() == 'Report a problem'

    client.login(active_user_with_permissions, mocker, service_one)
    logged_in_response = client.get(bat_phone_page)
    assert logged_in_response.status_code == 302
    assert logged_in_response.location == url_for('main.feedback', ticket_type='problem', _external=True)


@freeze_time('2016-12-12 12:00:00.000000')
@pytest.mark.parametrize('ticket_type', ['problem', 'question'])
def test_log_error_on_post(app_, mocker, ticket_type):
    mock_post = mocker.patch(
        'app.main.views.feedback.requests.post',
        return_value=Mock(
            status_code=401,
            json=lambda: {
                'error_code': 'invalid_auth',
                'error_message': 'Please provide a valid API key or token'}))
    with app_.test_request_context():
        mock_logger = mocker.patch.object(app_.logger, 'error')
        with app_.test_client() as client:
            with pytest.raises(InternalServerError):
                client.post(
                    url_for('main.feedback', ticket_type=ticket_type),
                    data={'feedback': "blah", 'name': "Steve Irwin", 'email_address': 'rip@gmail.com'})
            assert mock_post.called
            mock_logger.assert_called_with(
                "Deskpro create ticket request failed with {} '{}'".format(mock_post().status_code, mock_post().json()))


@pytest.mark.parametrize('logged_in', [True, False])
@pytest.mark.parametrize('urgent, anonymous, message', [

    (True, False, 'We’ll get back to you within 30 minutes.'),
    (False, False, 'We’ll get back to you by the next working day.'),

    (True, True, 'We’ll look into it within 30 minutes.'),
    (False, True, 'We’ll look into it by the next working day.'),

])
def test_thanks(
    client,
    mocker,
    api_user_active,
    mock_get_user,
    urgent,
    anonymous,
    message,
    logged_in,
):
    if logged_in:
        client.login(api_user_active)
    response = client.get(url_for('main.thanks', urgent=urgent, anonymous=anonymous))
    assert response.status_code == 200
    page = BeautifulSoup(response.data.decode('utf-8'), 'html.parser')
    assert ' '.join(page.find('main').find('p').text.split()) == message
