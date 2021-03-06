import pytest

from gidgethub import sansio
from gidgethub import abc as gh_abc

from bedevere import bpo


class FakeGH:

    def __init__(self, *, getitem=None):
        self._getitem_return = getitem
        self.patch_url = None
        self.patch_data = None
        self.data = None

    async def getitem(self, url):
        return self._getitem_return

    async def post(self, url, data):
        self.url = url
        self.data = data

    async def patch(self, url, data):
        self.patch_url = url
        self.patch_data = data


@pytest.mark.asyncio
async def test_set_status_failure():
    data = {
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "No issue in title",
            "issue_url": "issue URL",
        },
    }
    issue_data = {
        "labels": [
            {"name": "non-trivial"},
        ]
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    await bpo.set_status(event, gh)
    status = gh.data
    assert status["state"] == "failure"
    assert status["target_url"].startswith("https://devguide.python.org")
    assert status["context"] == "bedevere/issue-number"


@pytest.mark.asyncio
async def test_set_status_success():
    data = {
        "action": "opened",
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "[3.6] bpo-1234: an issue!",
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    status = gh.data
    assert status["state"] == "success"
    assert status["target_url"].endswith("issue1234")
    assert "1234" in status["description"]
    assert status["context"] == "bedevere/issue-number"
    assert "git-sha" in gh.url


@pytest.mark.asyncio
async def test_set_status_success_via_skip_issue_label():
    data = {
        "action": "opened",
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "No issue in title",
            "issue_url": "issue URL",
        },
    }
    issue_data = {
        "labels": [
            {"name": "skip issue"},
        ]
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH(getitem=issue_data)
    await bpo.router.dispatch(event, gh)
    status = gh.data
    assert status["state"] == "success"
    assert status["context"] == "bedevere/issue-number"
    assert "git-sha" in gh.url


@pytest.mark.asyncio
async def test_edit_title():
    data = {
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "bpo-1234: an issue!",
        },
        "action": "edited",
        "changes": {"title": "thingy"},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    assert gh.data is not None


@pytest.mark.asyncio
async def test_no_body_when_edit_title():
    data = {
        "action": "edited",
        "pull_request": {
            "url": "https://api.github.com/repos/python/cpython/pulls/5291",
            "title": "bpo-32636: Fix @asyncio.coroutine debug mode bug",
            "body": None,
            "statuses_url": "https://api.github.com/repos/python/cpython/statuses/98d60953c85df9f0f28e04322a4c4ebec7b180f4",
        },
        "changes": {
            "title": "bpo-32636: Fix @asyncio.coroutine debug mode bug exposed by #5250."
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    assert gh.patch_data is not None
    assert gh.patch_data['body'] == "\n\n<!-- issue-number: bpo-32636 -->\nhttps://bugs.python.org/issue32636\n<!-- /issue-number -->\n"


@pytest.mark.asyncio
async def test_edit_other_than_title():
    data = {
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "bpo-1234: an issue!",
        },
        "action": "edited",
        "changes": {"stuff": "thingy"},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    assert gh.data is None


@pytest.mark.asyncio
async def test_new_label_skip_issue_no_issue():
    data = {
        "action": "labeled",
        "label": {"name": "skip issue"},
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "An easy fix",
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    assert gh.data["state"] == "success"
    assert "git-sha" in gh.url


@pytest.mark.asyncio
async def test_new_label_skip_issue_with_issue_number():
    data = {
        "action": "labeled",
        "label": {"name": "skip issue"},
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "Revert bpo-1234: revert an easy fix",
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    status = gh.data
    assert status["state"] == "success"
    assert status["target_url"].endswith("issue1234")
    assert "1234" in status["description"]
    assert status["context"] == "bedevere/issue-number"
    assert "git-sha" in gh.url


@pytest.mark.asyncio
async def test_new_label_not_skip_issue():
    data = {
        "action": "labeled",
        "label": {"name": "non-trivial"},
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    assert gh.data is None


@pytest.mark.asyncio
async def test_removed_label_from_label_deletion():
    """When a label is completely deleted from a repo, it triggers an 'unlabeled'
    event, but the payload has no details about the removed label."""
    data = {
        "action": "unlabeled",
        # No "label" key.
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "bpo-1234: an issue!",
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    assert gh.data is None


@pytest.mark.asyncio
async def test_removed_label_skip_issue():
    data = {
        "action": "unlabeled",
        "label": {"name": "skip issue"},
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "title": "bpo-1234: an issue!",
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    status = gh.data
    assert status["state"] == "success"
    assert status["target_url"].endswith("issue1234")
    assert "1234" in status["description"]
    assert status["context"] == "bedevere/issue-number"
    assert "git-sha" in gh.url


@pytest.mark.asyncio
async def test_removed_label_non_skip_issue():
    data = {
        "action": "unlabeled",
        "label": {"name": "non-trivial"},
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    assert gh.data is None


@pytest.mark.asyncio
async def test_set_body_success():
    data = {
        "action": "opened",
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "url": "https://api.github.com/repos/blah/blah/pulls/1347",
            "title": "[3.6] bpo-1234: an issue!",
            "body": "This is the body of the PR.\nSecond line is here."
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    status = gh.patch_data
    assert "https://bugs.python.org/issue1234" in status["body"]
    assert "1347" in gh.patch_url


@pytest.mark.asyncio
async def test_set_body_failure():
    data = {
        "action": "opened",
        "pull_request": {
            "statuses_url": "https://api.github.com/blah/blah/git-sha",
            "url": "https://api.github.com/repos/blah/blah/pulls/1347",
            "title": "[3.6] bpo-1234: an issue!",
            "body": """The body.\n<!-- issue-number: bpo-1234 -->\n"https://bugs.python.org/issue1234"\n<!-- /issue-number -->"""
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="12345")
    gh = FakeGH()
    await bpo.router.dispatch(event, gh)
    assert gh.patch_data is None
    assert gh.patch_url is None
