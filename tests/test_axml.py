from __future__ import print_function
import unittest

import sys
from xml.dom import minidom
from lxml import etree

from androguard.core.bytecodes import axml
from androguard.core import bytecode

def is_valid_manifest(tree):
    # We can not really check much more...
    print(tree.tag, tree.attrib)
    if tree.tag == "manifest" and "package" in tree.attrib:
        return True
    return False

# text_compare and xml_compare are modified from 
# https://bitbucket.org/ianb/formencode/src/tip/formencode/doctest_xml_compare.py
def text_compare(t1, t2):
    if not t1 and not t2:
        return True
    if t1 == '*' or t2 == '*':
        return True
    return (t1 or '').strip() == (t2 or '').strip()

def xml_compare(x1, x2, reporter=None):
    """
    Compare two XML files
    x1 must be the plain version
    x2 must be the version generated by aapt
    """
    if x1.tag != x2.tag:
        if reporter:
            reporter('Tags do not match: %s and %s' % (x1.tag, x2.tag))
        return False
    for name, value in x1.attrib.items():
        if value[0] == "@" and x2.attrib.get(name)[0] == "@":
            # Can not be sure...
            pass
        elif x2.attrib.get(name) != value:
            if reporter:
                reporter('Attributes do not match: %s=%r, %s=%r'
                         % (name, value, name, x2.attrib.get(name)))
            return False
    for name in x2.attrib.keys():
        if name not in x1.attrib:
            if x2.tag == "application" and name == "{http://schemas.android.com/apk/res/android}debuggable":
                # Debug attribute might be added by aapt
                pass
            else:
                if reporter:
                    reporter('x2 has an attribute x1 is missing: %s'
                             % name)
                return False
    if not text_compare(x1.text, x2.text):
        if reporter:
            reporter('text: %r != %r' % (x1.text, x2.text))
        return False
    if not text_compare(x1.tail, x2.tail):
        if reporter:
            reporter('tail: %r != %r' % (x1.tail, x2.tail))
        return False
    cl1 = x1.getchildren()
    cl2 = x2.getchildren()
    if len(cl1) != len(cl2):
        if reporter:
            reporter('children length differs, %i != %i'
                     % (len(cl1), len(cl2)))
        return False
    i = 0
    for c1, c2 in zip(cl1, cl2):
        i += 1
        if not xml_compare(c1, c2, reporter=reporter):
            if reporter:
                reporter('children %i do not match: %s'
                         % (i, c1.tag))
            return False
    return True


class AXMLTest(unittest.TestCase):
    def testReplacement(self):
        """
        Test that the replacements for attributes, names and values are working
        :return:
        """
        # Fake, Empty AXML file
        a = axml.AXMLPrinter(b"\x03\x00\x08\x00\x24\x00\x00\x00"
                             b"\x01\x00\x1c\x00\x1c\x00\x00\x00"
                             b"\x00\x00\x00\x00\x00\x00\x00\x00"
                             b"\x00\x00\x00\x00"
                             b"\x00\x00\x00\x00\x00\x00\x00\x00")

        self.assertIsNotNone(a)

        self.assertEqual(a._fix_value(u"hello world"), u"hello world")
        self.assertEqual(a._fix_value(u"Foobar \u000a\u000d\u0b12"), u"Foobar \u000a\u000d\u0b12")
        self.assertEqual(a._fix_value(u"hello \U00011234"), u"hello \U00011234")
        self.assertEqual(a._fix_value(u"\uFFFF"), u"_")
        self.assertEqual(a._fix_value("hello\x00world"), u"hello")

        self.assertEqual(a._fix_name(u"foobar"), u"foobar")
        self.assertEqual(a._fix_name(u"5foobar"), u"_5foobar")
        self.assertEqual(a._fix_name(u"android:foobar"), u"foobar")
        self.assertEqual(a._fix_name(u"5:foobar"), u"_5_foobar")

    def testNoStringPool(self):
        """Test if a single header without string pool is rejected"""
        #                      |TYPE   |LENGTH |FILE LENGTH
        a = axml.AXMLPrinter(b"\x03\x00\x08\x00\x08\x00\x00\x00")
        self.assertFalse(a.is_valid())

    def testTooSmallFile(self):
        """Test if a very short file is rejected"""
        #                      |TYPE   |LENGTH |FILE LENGTH
        a = axml.AXMLPrinter(b"\x03\x00\x08\x00\x08\x00\x00")
        self.assertFalse(a.is_valid())

    def testWrongHeaderSize(self):
        """Test if a wrong header size is rejected"""
        a = axml.AXMLPrinter(b"\x03\x00\x10\x00\x2c\x00\x00\x00"
                             b"\x00\x00\x00\x00\x00\x00\x00\x00"
                             b"\x01\x00\x1c\x00\x1c\x00\x00\x00"
                             b"\x00\x00\x00\x00\x00\x00\x00\x00"
                             b"\x00\x00\x00\x00"
                             b"\x00\x00\x00\x00\x00\x00\x00\x00")
        self.assertFalse(a.is_valid())

    def testWrongStringPoolHeader(self):
        """Test if a wrong header type is rejected"""
        a = axml.AXMLPrinter(b"\x03\x00\x08\x00\x24\x00\x00\x00" b"\xDE\xAD\x1c\x00\x1c\x00\x00\x00"
                             b"\x00\x00\x00\x00\x00\x00\x00\x00"
                             b"\x00\x00\x00\x00"
                             b"\x00\x00\x00\x00\x00\x00\x00\x00")
        self.assertFalse(a.is_valid())

    def testWrongStringPoolSize(self):
        """Test if a wrong string pool header size is rejected"""
        a = axml.AXMLPrinter(b"\x03\x00\x08\x00\x2c\x00\x00\x00"
                             b"\x01\x00\x24\x00\x24\x00\x00\x00"
                             b"\x00\x00\x00\x00\x00\x00\x00\x00"
                             b"\x00\x00\x00\x00\x00\x00\x00\x00"
                             b"\x00\x00\x00\x00"
                             b"\x00\x00\x00\x00\x00\x00\x00\x00")
        self.assertFalse(a.is_valid())

    def testArscHeader(self):
        """Test if wrong arsc headers are rejected"""
        with self.assertRaises(AssertionError) as cnx:
            axml.ARSCHeader(bytecode.BuffHandle(b"\x02\x01"))
        self.assertTrue("Can not read over the buffer size" in str(cnx.exception))

        with self.assertRaises(AssertionError) as cnx:
            axml.ARSCHeader(bytecode.BuffHandle(b"\x02\x01\xFF\xFF\x08\x00\x00\x00"))
        self.assertTrue("smaller than header size" in str(cnx.exception))

        with self.assertRaises(AssertionError) as cnx:
            axml.ARSCHeader(bytecode.BuffHandle(b"\x02\x01\x01\x00\x08\x00\x00\x00"))
        self.assertTrue("declared header size is smaller than required size" in str(cnx.exception))

        with self.assertRaises(AssertionError) as cnx:
            axml.ARSCHeader(bytecode.BuffHandle(b"\x02\x01\x08\x00\x04\x00\x00\x00"))
        self.assertTrue("declared chunk size is smaller than required size" in str(cnx.exception))

        a = axml.ARSCHeader(bytecode.BuffHandle(b"\xCA\xFE\x08\x00\x10\x00\x00\x00"
                                                b"\xDE\xEA\xBE\xEF\x42\x42\x42\x42"))

        self.assertEqual(a.type, 0xFECA)
        self.assertEqual(a.header_size, 8)
        self.assertEqual(a.size, 16)
        self.assertEqual(a.start, 0)
        self.assertEqual(a.end, 16)
        self.assertEqual(repr(a), "<ARSCHeader idx='0x00000000' type='65226' header_size='8' size='16'>")

    def testAndroidManifest(self):
        filenames = [
            "examples/axml/AndroidManifest.xml",
            "examples/axml/AndroidManifest-Chinese.xml",
            "examples/axml/AndroidManifestDoubleNamespace.xml",
            "examples/axml/AndroidManifestExtraNamespace.xml",
            "examples/axml/AndroidManifest_InvalidCharsInAttribute.xml",
            "examples/axml/AndroidManifestLiapp.xml",
            "examples/axml/AndroidManifestMaskingNamespace.xml",
            "examples/axml/AndroidManifest_NamespaceInAttributeName.xml",
            "examples/axml/AndroidManifestNonZeroStyle.xml",
            "examples/axml/AndroidManifestNullbytes.xml",
            "examples/axml/AndroidManifestTextChunksXML.xml",
            "examples/axml/AndroidManifestUTF8Strings.xml",
            "examples/axml/AndroidManifestWithComment.xml",
            "examples/axml/AndroidManifest_WrongChunkStart.xml",
            "examples/axml/AndroidManifest-xmlns.xml",
        ]

        for filename in filenames:
            with open(filename, "rb") as fd:
                ap = axml.AXMLPrinter(fd.read())
            self.assertIsNotNone(ap)
            self.assertTrue(ap.is_valid())

            self.assertTrue(is_valid_manifest(ap.get_xml_obj()))

            e = minidom.parseString(ap.get_buff())
            self.assertIsNotNone(e)

    def testFileCompare(self):
        """
        Compare the binary version of a file with the plain text
        """
        binary = "examples/axml/AndroidManifest.xml"
        plain = "examples/android/TC/AndroidManifest.xml"

        with open(plain, "rb") as fp:
            x1 = etree.fromstring(fp.read())
        with open(binary, "rb") as fp:
            x2 = axml.AXMLPrinter(fp.read()).get_xml_obj()

        self.assertTrue(xml_compare(x1, x2, reporter=print))

    def testNonManifest(self):
        filenames = [
            "examples/axml/test.xml",
            "examples/axml/test1.xml",
            "examples/axml/test2.xml",
            "examples/axml/test3.xml",
        ]

        for filename in filenames:
            with open(filename, "rb") as fp:
                ap = axml.AXMLPrinter(fp.read())

            self.assertTrue(ap.is_valid())
            self.assertEqual(ap.get_xml_obj().tag, "LinearLayout")

            e = minidom.parseString(ap.get_buff())
            self.assertIsNotNone(e)

    def testNonZeroStyleOffset(self):
        """
        Test if a nonzero style offset in the string section causes problems
        if the counter is 0
        """
        filename = "examples/axml/AndroidManifestNonZeroStyle.xml"

        with open(filename, "rb") as f:
            ap = axml.AXMLPrinter(f.read())
        self.assertIsInstance(ap, axml.AXMLPrinter)
        self.assertTrue(ap.is_valid())

        e = minidom.parseString(ap.get_buff())
        self.assertIsNotNone(e)

    def testNonTerminatedString(self):
        """
        Test if non-null terminated strings are detected.
        This sample even segfaults aapt...
        """
        filename = "examples/axml/AndroidManifest_StringNotTerminated.xml"

        with self.assertRaises(AssertionError) as cnx:
            with open(filename, "rb") as f:
                ap = axml.AXMLPrinter(f.read())
        self.assertTrue("not null terminated" in str(cnx.exception))

    def testExtraNamespace(self):
        """
        Test if extra namespaces cause problems
        """
        filename = "examples/axml/AndroidManifestExtraNamespace.xml"

        with open(filename, "rb") as f:
            ap = axml.AXMLPrinter(f.read())
        self.assertIsInstance(ap, axml.AXMLPrinter)
        self.assertTrue(ap.is_valid())

        e = minidom.parseString(ap.get_buff())
        self.assertIsNotNone(e)

    def testTextChunksWithXML(self):
        """
        Test for Text chunks containing XML
        """
        filename = "examples/axml/AndroidManifestTextChunksXML.xml"

        with open(filename, "rb") as f:
            ap = axml.AXMLPrinter(f.read())
        self.assertIsInstance(ap, axml.AXMLPrinter)
        self.assertTrue(ap.is_valid())

        e = minidom.parseString(ap.get_buff())
        self.assertIsNotNone(e)

    def testWrongFilesize(self):
        """
        Assert that files with a broken filesize are not parsed
        """
        filename = "examples/axml/AndroidManifestWrongFilesize.xml"

        with open(filename, "rb") as f:
            a = axml.AXMLPrinter(f.read())
        self.assertFalse(a.is_valid())

    def testNullbytes(self):
        """
        Assert that Strings with nullbytes are handled correctly
        """
        filename = "examples/axml/AndroidManifestNullbytes.xml"

        with open(filename, "rb") as f:
            ap = axml.AXMLPrinter(f.read())
        self.assertIsInstance(ap, axml.AXMLPrinter)
        self.assertTrue(ap.is_valid())

        e = minidom.parseString(ap.get_buff())
        self.assertIsNotNone(e)

    def testMaskingNamespace(self):
        """
        Assert that Namespaces which are used in a tag and the tag is closed
        are actually correctly parsed.
        """
        filename = "examples/axml/AndroidManifestMaskingNamespace.xml"

        with open(filename, "rb") as f:
            ap = axml.AXMLPrinter(f.read())
        self.assertIsInstance(ap, axml.AXMLPrinter)
        self.assertTrue(ap.is_valid())

        e = minidom.parseString(ap.get_buff())
        self.assertIsNotNone(e)

    def testDoubleNamespace(self):
        """
        Test if weird namespace constelations cause problems
        """
        filename = "examples/axml/AndroidManifestDoubleNamespace.xml"

        with open(filename, "rb") as f:
            ap = axml.AXMLPrinter(f.read())
        self.assertIsInstance(ap, axml.AXMLPrinter)
        self.assertTrue(ap.is_valid())

        e = minidom.parseString(ap.get_buff())
        self.assertIsNotNone(e)

    def testPackers(self):
        """
        Assert that Packed files are read
        """
        filename = "examples/axml/AndroidManifestLiapp.xml"

        with open(filename, "rb") as f:
            ap = axml.AXMLPrinter(f.read())
        self.assertIsInstance(ap, axml.AXMLPrinter)
        self.assertTrue(ap.is_valid())

        self.assertTrue(ap.is_packed())


if __name__ == '__main__':
    unittest.main()
