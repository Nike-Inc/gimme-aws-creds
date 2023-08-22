"""Unit tests for gimme_aws_creds"""
import sys
import os
import unittest
from contextlib import contextmanager
from io import StringIO

import requests
import responses

import gimme_aws_creds.common as common_def
from gimme_aws_creds.aws import AwsResolver

def read_fixture(file_name):
    """Read a fixture file"""
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', file_name)
    with open(fixture_path, 'r', encoding='utf-8') as file:
        return file.read()
    
class TestAwsResolver(unittest.TestCase):
    """Class to test Okta Client Class.
       Mock is used to mock external calls"""

    @contextmanager
    def captured_output(self):
        """Capture StdErr and StdOut"""
        new_out, new_err = StringIO(), StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        try:
            sys.stdout, sys.stderr = new_out, new_err
            yield sys.stdout, sys.stderr
        finally:
            sys.stdout, sys.stderr = old_out, old_err

    def setUp(self):
        """Set up for the unit tests"""
        self.resolver = self.setUp_client(False)

        self.aws_signinpage = read_fixture('aws_legacy.html')
        self.aws_nextsigninpage = read_fixture('aws_nextjs.html')

        self.saml = "PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz48c2FtbDJwOlJlc3BvbnNlIHhtbG5zOnNhbWwycD0idXJuOm9hc2lzOm5hbWVzOnRjOlNBTUw6Mi4wOnByb3RvY29sIiBEZXN0aW5hdGlvbj0iaHR0cHM6Ly9zaWduaW4uYXdzLmFtYXpvbi5jb20vc2FtbCIgSUQ9ImlkMTMwMDM3MDA2MjEyMzQ1NDgwOTQxMTA2MzAiIElzc3VlSW5zdGFudD0iMjAxOC0wMy0xNFQyMjoxODo0MS44MzlaIiBWZXJzaW9uPSIyLjAiIHhtbG5zOnhzPSJodHRwOi8vd3d3LnczLm9yZy8yMDAxL1hNTFNjaGVtYSI+PHNhbWwyOklzc3VlciB4bWxuczpzYW1sMj0idXJuOm9hc2lzOm5hbWVzOnRjOlNBTUw6Mi4wOmFzc2VydGlvbiIgRm9ybWF0PSJ1cm46b2FzaXM6bmFtZXM6dGM6U0FNTDoyLjA6bmFtZWlkLWZvcm1hdDplbnRpdHkiPmh0dHA6Ly93d3cub2t0YS5jb20vZXhrYlhYWFhYWFhYWEh3MGg3PC9zYW1sMjpJc3N1ZXI+PGRzOlNpZ25hdHVyZSB4bWxuczpkcz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC8wOS94bWxkc2lnIyI+PGRzOlNpZ25lZEluZm8+PGRzOkNhbm9uaWNhbGl6YXRpb25NZXRob2QgQWxnb3JpdGhtPSJodHRwOi8vd3d3LnczLm9yZy8yMDAxLzEwL3htbC1leGMtYzE0biMiLz48ZHM6U2lnbmF0dXJlTWV0aG9kIEFsZ29yaXRobT0iaHR0cDovL3d3dy53My5vcmcvMjAwMS8wNC94bWxkc2lnLW1vcmUjcnNhLXNoYTI1NiIvPjxkczpSZWZlcmVuY2UgVVJJPSIjaWQxMzAwMzcwMDYyMTIzNDU0ODA5NDExMDYzMCI+PGRzOlRyYW5zZm9ybXM+PGRzOlRyYW5zZm9ybSBBbGdvcml0aG09Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvMDkveG1sZHNpZyNlbnZlbG9wZWQtc2lnbmF0dXJlIi8+PGRzOlRyYW5zZm9ybSBBbGdvcml0aG09Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvMTAveG1sLWV4Yy1jMTRuIyI+PGVjOkluY2x1c2l2ZU5hbWVzcGFjZXMgeG1sbnM6ZWM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvMTAveG1sLWV4Yy1jMTRuIyIgUHJlZml4TGlzdD0ieHMiLz48L2RzOlRyYW5zZm9ybT48L2RzOlRyYW5zZm9ybXM+PGRzOkRpZ2VzdE1ldGhvZCBBbGdvcml0aG09Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvMDQveG1sZW5jI3NoYTI1NiIvPjxkczpEaWdlc3RWYWx1ZT5SL3NNbEdPYzRDZjUyTDkwTEV5Ym52VTd5R2owMERLNkhmNWMwNTBQYnNVPTwvZHM6RGlnZXN0VmFsdWU+PC9kczpSZWZlcmVuY2U+PC9kczpTaWduZWRJbmZvPjxkczpTaWduYXR1cmVWYWx1ZT5MM2NnUlgwa0FXNFRtVjNheVFzVnF3R2JMQnhMWjkvS0dYdjN2U3hZNUFyQm5yeUd3dmJzSlFTVS9EbE05TzhJNHZHdi9YNVpPN0Y4L1M2Wll2TnNlVWF2akVXNmxPcmNtakpEYkY3MTJiZ0M2YnF3Z280Z1BYaVM3aXZPa3ZMK2JSamEyblo5NUUzQ0hVWThIamVFQ0FObTlMaWU0SVFveStGZGdxMlk4TmxzVHZZME91UVkzVlBYREdjTFNiVWxZL294N2FneENUaHNGc1FZbDdqR1VZblRkbVlqdXU5L3E2dExaL2wvRyt6ZVBPdVhnK1JnUzBuTVJiRmV5dXljQzlnZm04TWpDLzRxbjhoTjlyNDFRMUU3dXNKZ0RySkxhd1lhbXVPekI1TzREUTV4Y096QVgrOXZkUU0xdEhuYmUrck1LYUl1S0xjRTlaczA3cURaNEE9PTwvZHM6U2lnbmF0dXJlVmFsdWU+PGRzOktleUluZm8+PGRzOlg1MDlEYXRhPjxkczpYNTA5Q2VydGlmaWNhdGU+YmxhaGJsYWg8L2RzOlg1MDlDZXJ0aWZpY2F0ZT48L2RzOlg1MDlEYXRhPjwvZHM6S2V5SW5mbz48L2RzOlNpZ25hdHVyZT48c2FtbDJwOlN0YXR1cyB4bWxuczpzYW1sMnA9InVybjpvYXNpczpuYW1lczp0YzpTQU1MOjIuMDpwcm90b2NvbCI+PHNhbWwycDpTdGF0dXNDb2RlIFZhbHVlPSJ1cm46b2FzaXM6bmFtZXM6dGM6U0FNTDoyLjA6c3RhdHVzOlN1Y2Nlc3MiLz48L3NhbWwycDpTdGF0dXM+PHNhbWwyOkFzc2VydGlvbiB4bWxuczpzYW1sMj0idXJuOm9hc2lzOm5hbWVzOnRjOlNBTUw6Mi4wOmFzc2VydGlvbiIgSUQ9ImlkMTMwMDM3MDA2Mjc2MTQ5NjI5NjA5OTQxMiIgSXNzdWVJbnN0YW50PSIyMDE4LTAzLTE0VDIyOjE4OjQxLjgzOVoiIFZlcnNpb249IjIuMCIgeG1sbnM6eHM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvWE1MU2NoZW1hIj48c2FtbDI6SXNzdWVyIEZvcm1hdD0idXJuOm9hc2lzOm5hbWVzOnRjOlNBTUw6Mi4wOm5hbWVpZC1mb3JtYXQ6ZW50aXR5IiB4bWxuczpzYW1sMj0idXJuOm9hc2lzOm5hbWVzOnRjOlNBTUw6Mi4wOmFzc2VydGlvbiI+aHR0cDovL3d3dy5va3RhLmNvbS9leGtiWFhYWFhYWFhYSHcwaDc8L3NhbWwyOklzc3Vlcj48ZHM6U2lnbmF0dXJlIHhtbG5zOmRzPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwLzA5L3htbGRzaWcjIj48ZHM6U2lnbmVkSW5mbz48ZHM6Q2Fub25pY2FsaXphdGlvbk1ldGhvZCBBbGdvcml0aG09Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvMTAveG1sLWV4Yy1jMTRuIyIvPjxkczpTaWduYXR1cmVNZXRob2QgQWxnb3JpdGhtPSJodHRwOi8vd3d3LnczLm9yZy8yMDAxLzA0L3htbGRzaWctbW9yZSNyc2Etc2hhMjU2Ii8+PGRzOlJlZmVyZW5jZSBVUkk9IiNpZDEzMDAzNzAwNjI3NjE0OTYyOTYwOTk0MTIiPjxkczpUcmFuc2Zvcm1zPjxkczpUcmFuc2Zvcm0gQWxnb3JpdGhtPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwLzA5L3htbGRzaWcjZW52ZWxvcGVkLXNpZ25hdHVyZSIvPjxkczpUcmFuc2Zvcm0gQWxnb3JpdGhtPSJodHRwOi8vd3d3LnczLm9yZy8yMDAxLzEwL3htbC1leGMtYzE0biMiPjxlYzpJbmNsdXNpdmVOYW1lc3BhY2VzIHhtbG5zOmVjPSJodHRwOi8vd3d3LnczLm9yZy8yMDAxLzEwL3htbC1leGMtYzE0biMiIFByZWZpeExpc3Q9InhzIi8+PC9kczpUcmFuc2Zvcm0+PC9kczpUcmFuc2Zvcm1zPjxkczpEaWdlc3RNZXRob2QgQWxnb3JpdGhtPSJodHRwOi8vd3d3LnczLm9yZy8yMDAxLzA0L3htbGVuYyNzaGEyNTYiLz48ZHM6RGlnZXN0VmFsdWU+U0VNekJ3cHh1ZTgvLytVdTNwUHY0b1RTRzZ1blU5YXh1SlZreWQ2OXdRQT08L2RzOkRpZ2VzdFZhbHVlPjwvZHM6UmVmZXJlbmNlPjwvZHM6U2lnbmVkSW5mbz48ZHM6U2lnbmF0dXJlVmFsdWU+R00zdmlhaklCK0p2RnpDSTF6eERIUWtMRmljc0JmSlorYTUxeksxT0p5YmRFR1hMNlN4VkY4MVFMK3FhcHNPQ1ZHbmtkMWtua20zYTBTMFVjbDRpTnNtRDFvT1g1UGliQjlFNkdXWHd3eUo5bTJRV1h4SUViRzVReXpWMGRJQmNKTTBiZk1XTEg1M3JiS0tDUnd5N0pYa0tNYS9leWFQTzNuVUZBVWFmbnEvOHZkd2hsTEJwTDhnWFB3RmJUL3dhK2FzMUROL3JQTDREaUxvUWpkZ2JMWlBDNUVXY3BpT0VBYjcreWg5OTFIaVlqOWN2NUFnME56VTJMTHNwcy94cjh6YzIzaEsrLys3UUpSS2taVkI3am0za0J3OEhaeDRxOUxqOWx3VlNwc1JHZy8xcEFCS25TVFo3VUp6YTEzMEZDWFVjaWZvWUxyODJ1M1ZiUzdEcjJRPT08L2RzOlNpZ25hdHVyZVZhbHVlPjxkczpLZXlJbmZvPjxkczpYNTA5RGF0YT48ZHM6WDUwOUNlcnRpZmljYXRlPmJsYWhibGFoPC9kczpYNTA5Q2VydGlmaWNhdGU+PC9kczpYNTA5RGF0YT48L2RzOktleUluZm8+PC9kczpTaWduYXR1cmU+PHNhbWwyOlN1YmplY3QgeG1sbnM6c2FtbDI9InVybjpvYXNpczpuYW1lczp0YzpTQU1MOjIuMDphc3NlcnRpb24iPjxzYW1sMjpOYW1lSUQgRm9ybWF0PSJ1cm46b2FzaXM6bmFtZXM6dGM6U0FNTDoyLjA6bmFtZWlkLWZvcm1hdDp1bnNwZWNpZmllZCI+am9obi5kb2VAbXljb3JwLmNvbTwvc2FtbDI6TmFtZUlEPjxzYW1sMjpTdWJqZWN0Q29uZmlybWF0aW9uIE1ldGhvZD0idXJuOm9hc2lzOm5hbWVzOnRjOlNBTUw6Mi4wOmNtOmJlYXJlciI+PHNhbWwyOlN1YmplY3RDb25maXJtYXRpb25EYXRhIE5vdE9uT3JBZnRlcj0iMjAxOC0wMy0xNFQyMjoyMzo0MS44MzlaIiBSZWNpcGllbnQ9Imh0dHBzOi8vc2lnbmluLmF3cy5hbWF6b24uY29tL3NhbWwiLz48L3NhbWwyOlN1YmplY3RDb25maXJtYXRpb24+PC9zYW1sMjpTdWJqZWN0PjxzYW1sMjpDb25kaXRpb25zIE5vdEJlZm9yZT0iMjAxOC0wMy0xNFQyMjoxMzo0MS44MzlaIiBOb3RPbk9yQWZ0ZXI9IjIwMTgtMDMtMTRUMjI6MjM6NDEuODM5WiIgeG1sbnM6c2FtbDI9InVybjpvYXNpczpuYW1lczp0YzpTQU1MOjIuMDphc3NlcnRpb24iPjxzYW1sMjpBdWRpZW5jZVJlc3RyaWN0aW9uPjxzYW1sMjpBdWRpZW5jZT51cm46YW1hem9uOndlYnNlcnZpY2VzPC9zYW1sMjpBdWRpZW5jZT48L3NhbWwyOkF1ZGllbmNlUmVzdHJpY3Rpb24+PC9zYW1sMjpDb25kaXRpb25zPjxzYW1sMjpBdXRoblN0YXRlbWVudCBBdXRobkluc3RhbnQ9IjIwMTgtMDMtMTRUMjI6MTg6MTAuOTIwWiIgU2Vzc2lvbkluZGV4PSJpZDE1MjEwNjU5MjE4MzkuMTM2MTc3OTMwOSIgeG1sbnM6c2FtbDI9InVybjpvYXNpczpuYW1lczp0YzpTQU1MOjIuMDphc3NlcnRpb24iPjxzYW1sMjpBdXRobkNvbnRleHQ+PHNhbWwyOkF1dGhuQ29udGV4dENsYXNzUmVmPnVybjpvYXNpczpuYW1lczp0YzpTQU1MOjIuMDphYzpjbGFzc2VzOlBhc3N3b3JkUHJvdGVjdGVkVHJhbnNwb3J0PC9zYW1sMjpBdXRobkNvbnRleHRDbGFzc1JlZj48L3NhbWwyOkF1dGhuQ29udGV4dD48L3NhbWwyOkF1dGhuU3RhdGVtZW50PjxzYW1sMjpBdHRyaWJ1dGVTdGF0ZW1lbnQgeG1sbnM6c2FtbDI9InVybjpvYXNpczpuYW1lczp0YzpTQU1MOjIuMDphc3NlcnRpb24iPjxzYW1sMjpBdHRyaWJ1dGUgTmFtZT0iaHR0cHM6Ly9hd3MuYW1hem9uLmNvbS9TQU1ML0F0dHJpYnV0ZXMvUm9sZSIgTmFtZUZvcm1hdD0idXJuOm9hc2lzOm5hbWVzOnRjOlNBTUw6Mi4wOmF0dHJuYW1lLWZvcm1hdDp1cmkiPjxzYW1sMjpBdHRyaWJ1dGVWYWx1ZSB4bWxuczp4cz0iaHR0cDovL3d3dy53My5vcmcvMjAwMS9YTUxTY2hlbWEiIHhtbG5zOnhzaT0iaHR0cDovL3d3dy53My5vcmcvMjAwMS9YTUxTY2hlbWEtaW5zdGFuY2UiIHhzaTp0eXBlPSJ4czpzdHJpbmciPmFybjphd3M6aWFtOjo5ODc2NTQzMjE5ODc6c2FtbC1wcm92aWRlci9PS1RBLUlEUCxhcm46YXdzOmlhbTo6OTg3NjU0MzIxOTg3OnJvbGUvdGVzdHJvbGUzPC9zYW1sMjpBdHRyaWJ1dGVWYWx1ZT48c2FtbDI6QXR0cmlidXRlVmFsdWUgeG1sbnM6eHM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvWE1MU2NoZW1hIiB4bWxuczp4c2k9Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvWE1MU2NoZW1hLWluc3RhbmNlIiB4c2k6dHlwZT0ieHM6c3RyaW5nIj5hcm46YXdzOmlhbTo6OTg3NjU0MzIxOTg3OnNhbWwtcHJvdmlkZXIvT0tUQS1JRFAsYXJuOmF3czppYW06Ojk4NzY1NDMyMTk4Nzpyb2xlL3Rlc3Ryb2xlNDwvc2FtbDI6QXR0cmlidXRlVmFsdWU+PHNhbWwyOkF0dHJpYnV0ZVZhbHVlIHhtbG5zOnhzPSJodHRwOi8vd3d3LnczLm9yZy8yMDAxL1hNTFNjaGVtYSIgeG1sbnM6eHNpPSJodHRwOi8vd3d3LnczLm9yZy8yMDAxL1hNTFNjaGVtYS1pbnN0YW5jZSIgeHNpOnR5cGU9InhzOnN0cmluZyI+YXJuOmF3czppYW06Ojk4NzY1NDMyMTk4NzpzYW1sLXByb3ZpZGVyL09LVEEtSURQLGFybjphd3M6aWFtOjo5ODc2NTQzMjE5ODc6cm9sZS90ZXN0cm9sZTU8L3NhbWwyOkF0dHJpYnV0ZVZhbHVlPjxzYW1sMjpBdHRyaWJ1dGVWYWx1ZSB4bWxuczp4cz0iaHR0cDovL3d3dy53My5vcmcvMjAwMS9YTUxTY2hlbWEiIHhtbG5zOnhzaT0iaHR0cDovL3d3dy53My5vcmcvMjAwMS9YTUxTY2hlbWEtaW5zdGFuY2UiIHhzaTp0eXBlPSJ4czpzdHJpbmciPmFybjphd3M6aWFtOjowMTIzNDU2Nzg5MDE6c2FtbC1wcm92aWRlci9PS1RBLUlEUCxhcm46YXdzOmlhbTo6MDEyMzQ1Njc4OTAxOnJvbGUvdGVzdHJvbGUxPC9zYW1sMjpBdHRyaWJ1dGVWYWx1ZT48c2FtbDI6QXR0cmlidXRlVmFsdWUgeG1sbnM6eHM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvWE1MU2NoZW1hIiB4bWxuczp4c2k9Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvWE1MU2NoZW1hLWluc3RhbmNlIiB4c2k6dHlwZT0ieHM6c3RyaW5nIj5hcm46YXdzOmlhbTo6MDEyMzQ1Njc4OTAxOnNhbWwtcHJvdmlkZXIvT0tUQS1JRFAsYXJuOmF3czppYW06OjAxMjM0NTY3ODkwMTpyb2xlL3Rlc3Ryb2xlMjwvc2FtbDI6QXR0cmlidXRlVmFsdWU+PC9zYW1sMjpBdHRyaWJ1dGU+PHNhbWwyOkF0dHJpYnV0ZSBOYW1lPSJodHRwczovL2F3cy5hbWF6b24uY29tL1NBTUwvQXR0cmlidXRlcy9Sb2xlU2Vzc2lvbk5hbWUiIE5hbWVGb3JtYXQ9InVybjpvYXNpczpuYW1lczp0YzpTQU1MOjIuMDphdHRybmFtZS1mb3JtYXQ6YmFzaWMiPjxzYW1sMjpBdHRyaWJ1dGVWYWx1ZSB4bWxuczp4cz0iaHR0cDovL3d3dy53My5vcmcvMjAwMS9YTUxTY2hlbWEiIHhtbG5zOnhzaT0iaHR0cDovL3d3dy53My5vcmcvMjAwMS9YTUxTY2hlbWEtaW5zdGFuY2UiIHhzaTp0eXBlPSJ4czpzdHJpbmciPmpvaG4uZG9lQG15Y29ycC5jb208L3NhbWwyOkF0dHJpYnV0ZVZhbHVlPjwvc2FtbDI6QXR0cmlidXRlPjxzYW1sMjpBdHRyaWJ1dGUgTmFtZT0iaHR0cHM6Ly9hd3MuYW1hem9uLmNvbS9TQU1ML0F0dHJpYnV0ZXMvU2Vzc2lvbkR1cmF0aW9uIiBOYW1lRm9ybWF0PSJ1cm46b2FzaXM6bmFtZXM6dGM6U0FNTDoyLjA6YXR0cm5hbWUtZm9ybWF0OmJhc2ljIj48c2FtbDI6QXR0cmlidXRlVmFsdWUgeG1sbnM6eHM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvWE1MU2NoZW1hIiB4bWxuczp4c2k9Imh0dHA6Ly93d3cudzMub3JnLzIwMDEvWE1MU2NoZW1hLWluc3RhbmNlIiB4c2k6dHlwZT0ieHM6c3RyaW5nIj4zNjAwPC9zYW1sMjpBdHRyaWJ1dGVWYWx1ZT48L3NhbWwyOkF0dHJpYnV0ZT48L3NhbWwyOkF0dHJpYnV0ZVN0YXRlbWVudD48L3NhbWwyOkFzc2VydGlvbj48L3NhbWwycDpSZXNwb25zZT4="

        self.roles = []
        self.roles.append(common_def.RoleSet(idp='arn:aws:iam::012345678901:saml-provider/OKTA-IDP',
                                             role='arn:aws:iam::012345678901:role/testrole1',
                                             friendly_account_name='Account: testaccount1 (012345678901)',
                                             friendly_role_name='testrole1'))
        self.roles.append(common_def.RoleSet(idp='arn:aws:iam::012345678901:saml-provider/OKTA-IDP',
                                             role='arn:aws:iam::012345678901:role/testrole2',
                                             friendly_account_name='Account: testaccount1 (012345678901)',
                                             friendly_role_name='testrole2'))
        self.roles.append(common_def.RoleSet(idp='arn:aws:iam::987654321987:saml-provider/OKTA-IDP',
                                             role='arn:aws:iam::987654321987:role/testrole3',
                                             friendly_account_name='Account: 987654321987',
                                             friendly_role_name='testrole3'))
        self.roles.append(common_def.RoleSet(idp='arn:aws:iam::987654321987:saml-provider/OKTA-IDP',
                                             role='arn:aws:iam::987654321987:role/testrole4',
                                             friendly_account_name='Account: 987654321987',
                                             friendly_role_name='testrole4'))
        self.roles.append(common_def.RoleSet(idp='arn:aws:iam::987654321987:saml-provider/OKTA-IDP',
                                             role='arn:aws:iam::987654321987:role/testrole5',
                                             friendly_account_name='Account: 987654321987',
                                             friendly_role_name='testrole5'))

    def setUp_client(self, verify_ssl_certs):
        resolver = AwsResolver(verify_ssl_certs)
        resolver.req_session = requests
        return resolver

    @responses.activate
    def test_enumerate_saml_roles(self):
        """Test parsing the roles from SAML assrtion & AwsSigninPage"""
        responses.add(responses.POST, 'https://signin.aws.amazon.com/saml', status=200, body=self.aws_signinpage)
        result = self.resolver._enumerate_saml_roles(self.saml, 'https://signin.aws.amazon.com/saml')
        self.assertEqual(result[0], self.roles[0])
        self.assertEqual(result[1], self.roles[1])
        self.assertEqual(result[2], self.roles[2])
        self.assertEqual(result[3], self.roles[3])
        self.assertEqual(result[4], self.roles[4])

    @responses.activate
    def test_enumerate_saml_roles_nextjs(self):
        """Test parsing the roles from SAML assrtion & NextJS AwsSigninPage"""
        responses.add(responses.POST, 'https://signin.aws.amazon.com/saml', status=200, body=self.aws_nextsigninpage)
        result = self.resolver._enumerate_saml_roles(self.saml, 'https://signin.aws.amazon.com/saml')
        self.assertEqual(result[0], self.roles[0])
        self.assertEqual(result[1], self.roles[1])
        self.assertEqual(result[2], self.roles[2])
        self.assertEqual(result[3], self.roles[3])
        self.assertEqual(result[4], self.roles[4])

    def test_display_role(self):
        """Test the roles are well displayed (grouped/indented by account)"""
        self.display_role = []
        self.display_role.append('Account: testaccount1 (012345678901)')
        self.display_role.append('      [ 0 ]: testrole1')
        self.display_role.append('      [ 1 ]: testrole2')
        self.display_role.append('Account: 987654321987')
        self.display_role.append('      [ 2 ]: testrole3')
        self.display_role.append('      [ 3 ]: testrole4')
        self.display_role.append('      [ 4 ]: testrole5')

        result = self.resolver._display_role(self.roles)
        self.assertEqual(result[0], self.display_role[0])
        self.assertEqual(result[1], self.display_role[1])
        self.assertEqual(result[2], self.display_role[2])
        self.assertEqual(result[3], self.display_role[3])
        self.assertEqual(result[4], self.display_role[4])
        self.assertEqual(result[5], self.display_role[5])
        self.assertEqual(result[6], self.display_role[6])
		
