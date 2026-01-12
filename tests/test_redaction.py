
import unittest

from redactor.redactor import Redactor, RedactedText

#@unittest.skip("disabled due to model load times")
class RedactionTestCase(unittest.TestCase):

    def test_redacted_text(self):
        redacted_text = "Alert: Chris [LastName1] and Elena [LastName2] detected outage near [Address1]. Phone [Phone1]."
        expected_text = "Alert: Chris Garcia and Elena Lopez detected outage near 44 Beacon St, Boston, MA 02108. Phone 206-555-9988."
        props = {
            "[LastName1]": "Garcia",
            "[LastName2]": "Lopez",
            "[Address1]": "44 Beacon St, Boston, MA 02108",
            "[Phone1]": "206-555-9988"
        }

        redacted = RedactedText(redacted_text, props)
        self.assertEqual(expected_text, redacted.unredact())


    def test_redactor(self):
        text = "Alert: Chris Garcia and Elena Lopez detected outage near 3039 Beacon St, Boston, MA 02108. Phone 206-555-9988."
        expected_props = {
            "[LastName1]": "Garcia",
            "[LastName2]": "Lopez",
            "[Address1]": "3039 Beacon St",
            "[City1]": "Boston",
            "[State1]": "MA",
            "[Zip1]": "02108",
            "[Phone1]": "206-555-9988"
        }

        redactor = Redactor()
        redacted = redactor.redact_text(text)

        #print("Input:", text)
        print("Redacted:", redacted)
        print("Fields:", redacted.fields)
        # print("Unredacted:", redacted.unredact())

        for key, value in expected_props.items():
            self.assertTrue(key in redacted.fields, f"Missing expected key: {key}, not in redacted fields: {redacted.fields} ")
            self.assertEqual(expected_props[key], redacted.fields[key])

        unredacted = redacted.unredact()
        self.assertEqual(unredacted, text)
