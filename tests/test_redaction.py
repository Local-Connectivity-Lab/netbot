
import unittest

from redactor.redactor import Redactor, RedactedText


class RedactionTestCase(unittest.TestCase):

    def test_redacted_text(self):
        redacted_text = "Alert: Chris [lastname1] and Elena [lastname2] detected outage near [address1]. Phone [phone1]."
        expected_text = "Alert: Chris Garcia and Elena Lopez detected outage near 44 Beacon St, Boston, MA 02108. Phone 206-555-9988."
        props = {
            "lastname1": "Garcia",
            "lastname2": "Lopez",
            "address1": "44 Beacon St, Boston, MA 02108",
            "phone1": "206-555-9988"
        }

        redacted = RedactedText(redacted_text, props)
        self.assertEqual(expected_text, redacted.unredact())


    def test_redactor(self):
        text = "Alert: Chris Garcia and Elena Lopez detected outage near 44 Beacon St, Boston, MA 02108. Phone 206-555-9988."
        expected_props = {
            "lastname1": "Garcia",
            "lastname2": "Lopez",
            "address1": "44 Beacon St, Boston, MA 02108",
            "phone1": "206-555-9988"
        }

        redactor = Redactor()
        redacted = redactor.redact_text(text)

        # print("Input:", text)
        print("Redacted:", redacted)
        # print("Fields:", redacted.fields)
        # print("Unredacted:", redacted.unredact())

        for key, value in expected_props.items():
            self.assertTrue(key in redacted.fields, f"Missing expected key: {key}, not in redacted fields: {redacted.fields} ")
            self.assertEqual(expected_props[key], redacted.fields[key])

        unredacted = redacted.unredact()
        self.assertEqual(unredacted, text)
