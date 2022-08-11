import logging
import os
import shutil
import tempfile
import asyncio
from xml.etree import ElementTree

import requests
import server
from core.pipeline import Pipeline
from core.utils.daisy_pipeline import DaisyPipelineJob
from core.utils.epub import Epub
from core.utils.filesystem import Filesystem
from core.utils.mathml_to_text import Mathml_validator
from core.utils.xslt import Xslt


class IncomingNordic(Pipeline):
    """
    IncomingNordic class
    """
    uid = "incoming-nordic"
    title = "Validering av Nordisk EPUB 3"
    epubTitle = ""
    labels = ["EPUB", "Statped"]
    publication_format = None
    expected_processing_time = 1400
    epub = None
    epub_fixed = None
    epub_fixed_obj = None
    epub_unzipped = None
    editionId = ""
    sourcePath = None
    temp_noimages_epubdir_obj = None
    temp_noimages_epubdir = ""
    temp_noimages_epub = None
    nav_path = ""

    ace_cli = os.environ.get("ACE_CLI", None)

    def __init__(self, *args, **kwargs):
        # Define variables
        for key, value in kwargs.items():
            setattr(self, key, value)
        # Initialize the superclass
        super().__init__(*args, **kwargs)
        # Generate source path from editionId
        self.sourcePath = os.path.join(os.environ.get(
            "PRODSYS_SOURCE_DIR"), self.editionId)
        # Initialize the EPUB object
        self.epub = Epub(self.utils.report, path=self.sourcePath)

    def run(self):
        """
        Run the pipeline
        """
        try:
            logging.info(f"Running pipeline: '{self.uid}'")
            loop = asyncio.get_event_loop()

            wf1 = asyncio.gather(self.check_epub())
            wf2 = asyncio.gather(
                self.copy_epub_and_replace_images(),
                self.validate_mathml(self.epub_fixed, self.epub_unzipped, self.nav_path),
                self.validate_epub_with_daisy_ace(self.epub_fixed)
            )
            wf3 = asyncio.gather(self.finalize())

            all_workflows = asyncio.gather(wf1, wf2, wf3)

            # Run the pipeline
            loop.run_until_complete(all_workflows)

        except Exception as e:
            logging.error(f"Failed pipeline: '{self.uid}'")
            logging.error(e)
            raise e
        finally:
            logging.info(f"Finished pipeline: '{self.uid}'")
            loop.close()
            return True

    @asyncio.coroutine
    async def check_epub(self):
        """
        Check the EPUB
        """
        self.epubTitle = ""
        try:
            self.epubTitle = " (" + self.epub.meta("dc:title") + ") "
        except Exception:
            pass
        # sjekk at dette er en EPUB
        if not self.epub.isepub():
            self.utils.report.title = self.title + ": " + \
                self.book["name"] + " feilet 😭👎" + self.epubTitle
            return False

        if not self.epub.identifier():
            self.utils.report.error(
                self.book["name"] + ": Klarte ikke å bestemme boknummer basert på dc:identifier.")
            self.utils.report.title = self.title + ": " + \
                self.book["name"] + " feilet 😭👎" + self.epubTitle
            return False

        
        complete, incomplete = await asyncio.wait(self.create_copy_of_epub(self.epub))
        return complete.return_value

    @asyncio.coroutine
    async def copy_epub_and_replace_images(self):
        """
        Create a copy of the EPUB with empty images and replace them with empty images
        """
        self.utils.report.info("Lager en kopi av EPUBen med tomme bildefiler")
        temp_noimages_epubdir_obj = tempfile.TemporaryDirectory()
        temp_noimages_epubdir = temp_noimages_epubdir_obj.name
        Filesystem.copy(self.utils.report, self.epub.asDir(),
                        temp_noimages_epubdir)

        complete, incomplete = await asyncio.wait(self.replace_images(temp_noimages_epubdir))
        return complete.return_value

    @asyncio.coroutine
    async def replace_images(self, temp_noimages_epubdir):
        """
        Replace images
        """
        self.utils.report.info("Erstatter bilder med tomme bildefiler")
        if os.path.isdir(os.path.join(temp_noimages_epubdir, "EPUB", "images")):
            opf_image_references = []
            temp_xml_obj = tempfile.NamedTemporaryFile()
            temp_xml = temp_xml_obj.name
            opf_image_references = []
            html_image_references = {}
            for root, dirs, files in os.walk(os.path.join(temp_noimages_epubdir, "EPUB")):
                for file in files:
                    if file.endswith(".opf"):
                        opf_file = os.path.join(root, file)
                        self.utils.report.info(
                            "Fjerner alle bildereferanser fra OPFen, og erstatter med en referanse til dummy.jpg...")
                        opf_xml_document = ElementTree.parse(opf_file)
                        opf_xml = opf_xml_document.getroot()
                        image_items = opf_xml.xpath(
                            "//*[local-name()='item' and starts-with(@media-type, 'image/')]")
                        replaced = False
                        for image_item in image_items:
                            if image_item.attrib["href"] not in opf_image_references:
                                opf_image_references.append(
                                    image_item.attrib["href"])

                            if image_item.get("href") == "images/cover.jpg":
                                pass  # don't change the reference to cover.jpg

                            elif not replaced:
                                image_item.attrib["href"] = "images/dummy.jpg"
                                replaced = True

                            else:
                                image_item.getparent().remove(image_item)

                        opf_xml_document.write(
                            opf_file, method='XML', xml_declaration=True, encoding='UTF-8', pretty_print=False)

                    if file.endswith(".xhtml"):
                        html_file = os.path.join(root, file)

                        html_xml_document = ElementTree.parse(html_file)
                        html_xml = html_xml_document.getroot()
                        image_references = html_xml.xpath(
                            "//@href | //@src | //@altimg")
                        for reference in image_references:
                            path = reference.split("#")[0]
                            if path.startswith("images/"):
                                if path not in html_image_references:
                                    html_image_references[path] = []
                                html_image_references[path].append(file)

                        self.utils.report.info(
                            "Erstatter alle bildereferanser med images/dummy.jpg...")
                        self.utils.report.debug("dummy-jpg.xsl")
                        self.utils.report.debug("    source = " + html_file)
                        self.utils.report.debug("    target = " + temp_xml)
                        xslt = Xslt(self,
                                    stylesheet=os.path.join(
                                        Xslt.xslt_dir, IncomingNordic.uid, "dummy-jpg.xsl"),
                                    source=html_file,
                                    target=temp_xml)
                        if not xslt.success:
                            self.utils.report.title = self.title + ": " + \
                                self.epub.identifier() + " feilet 😭👎" + self.epubTitle
                            return False
                        shutil.copy(temp_xml, html_file)

                        self.validate_image_files(
                            opf_image_references, html_image_references)

                await asyncio.wait(self.validate_image_files(opf_image_references, html_image_references))
        
        return True

    @asyncio.coroutine
    async def validate_image_files(self, opf_image_references, html_image_references):
        """
        Validate image files
        """
        # validate for the presence of image files here, since epubcheck won't be able to do it anymore after we change the EPUB
        image_files_present = []
        for root, dirs, files in os.walk(os.path.join(self.temp_noimages_epubdir, "EPUB", "images")):
            for file in files:
                fullpath = os.path.join(root, file)
                relpath = os.path.relpath(
                    fullpath, os.path.join(self.temp_noimages_epubdir, "EPUB"))
                image_files_present.append(relpath)
        image_error = False
        for file in image_files_present:
            if file not in opf_image_references:
                self.utils.report.error(
                    "Bildefilen er ikke deklarert i OPFen: " + file)
                image_error = True
        for file in opf_image_references:
            if file not in image_files_present:
                self.utils.report.error(
                    "Bildefilen er deklarert i OPFen, men finnes ikke: " + file)
                image_error = True
        for file in html_image_references:
            if file not in opf_image_references:
                self.utils.report.error("Bildefilen er deklarert i HTMLen, men finnes ikke: " + file
                                        + " (deklarert i: " + ", ".join(html_image_references[file]) + ")")
                image_error = True
        if image_error:
            self.utils.report.title = self.title + ": " + \
                self.epub.identifier() + " feilet 😭👎" + self.epubTitle
            return False

        for root, dirs, files in os.walk(os.path.join(self.temp_noimages_epubdir, "EPUB", "images")):
            for file in files:
                if file == "cover.jpg":
                    continue  # don't delete the cover file
                fullpath = os.path.join(root, file)
                os.remove(fullpath)
        shutil.copy(os.path.join(Xslt.xslt_dir, IncomingNordic.uid, "reference-files", "demobilde.jpg"),
                    os.path.join(self.temp_noimages_epubdir, "EPUB", "images", "dummy.jpg"))

        temp_noimages_epub = Epub(
            self.utils.report, self.temp_noimages_epubdir)

        complete, incomplete = await asyncio.wait(self.validate_epub(temp_noimages_epub))
        return complete.return_value

    @asyncio.coroutine
    async def validate_epub(self, temp_noimages_epub):
        """
        Validate the EPUB.
        """
        self.utils.report.info(
            "Validerer EPUB med epubcheck og nordiske retningslinjer...")
        epub_noimages_file = temp_noimages_epub.asFile()
        with DaisyPipelineJob(self,
                              "nordic-epub3-validate",
                              {"epub": os.path.basename(epub_noimages_file)},
                              priority="high",
                              pipeline_and_script_version=[
                                  ("1.13.6", "1.4.6"),
                                  ("1.13.4", "1.4.5"),
                                  ("1.12.1", "1.4.2"),
                                  ("1.11.1-SNAPSHOT", "1.3.0"),
                              ],
                              context={
                                  os.path.basename(epub_noimages_file): epub_noimages_file
                              }) as dp2_job:

            # get validation report
            report_file = os.path.join(
                dp2_job.dir_output, "html-report/report.xhtml")
            if os.path.isfile(report_file):
                with open(report_file, 'r') as result_report:
                    self.utils.report.attachment(result_report.readlines(),
                                                 os.path.join(
                                                     self.utils.report.reportDir(), "report.html"),
                                                 "SUCCESS" if dp2_job.status == "SUCCESS" else "ERROR")

            if dp2_job.status != "SUCCESS":
                self.utils.report.error("Klarte ikke å validere boken")
                self.utils.report.title = self.title + ": " + \
                    self.epub.identifier() + " feilet 😭👎" + self.epubTitle
                return False

        return True

    @asyncio.coroutine
    async def create_copy_of_epub(self, epub):
        """
        Create a copy of the epub.
        """
        self.utils.report.debug("Making a copy of the EPUB to work on…")
        self.epub_fixed, self.epub_fixed_obj = epub.copy()
        self.epub_unzipped = self.epub_fixed.asDir()
        self.nav_path = os.path.join(
            self.epub_unzipped, self.epub_fixed.nav_path())
        return True

    @asyncio.coroutine
    async def validate_mathml(self, epub_fixed, epub_unzipped, nav_path):
        """
        Validate MathML in the epub.
        """
        self.utils.report.info("Validating MathML elements...")
        mathML_validation_result = True
        mathml_error_count = 0
        mathml_errors_not_shown = 0
        mathml_report_errors_max = 10

        for root, dirs, files in os.walk(epub_unzipped):
            for f in files:
                file = os.path.join(root, f)
                if not file.endswith(".xhtml") or file is nav_path:
                    continue
                self.utils.report.info("Checking MathML in " + file)
                mathml_validation = Mathml_validator(
                    self, source=file, report_errors_max=mathml_report_errors_max)
                if not mathml_validation.success:
                    mathml_error_count += mathml_validation.error_count
                    mathml_errors_not_shown += max(
                        (mathml_validation.error_count - mathml_report_errors_max), 0)
                    if mathml_error_count > mathml_report_errors_max:
                        # don't put any more errors for the other HTML documents in the main report
                        mathml_report_errors_max = 0
                    mathML_validation_result = False

        if mathml_errors_not_shown > 0:
            self.utils.report.error(
                "{} additional MathML errors not shown in the main report. Check the log for details.".format(mathml_errors_not_shown))
        if mathML_validation_result is False:
            return False

        self.utils.report.debug(
            "Making sure that the EPUB has the correct file and directory permissions…")
        epub_fixed.fix_permissions()

        return mathML_validation_result

    @asyncio.coroutine
    async def validate_epub_with_daisy_ace(self, epub_fixed):
        """
        Validate the EPUB with Daisy ACE.
        """
        # send epub to daisy-ace to get a report
        res = requests.post(os.environ.daisy_ace_url, files={
                            "epub": open(epub_fixed.asFile(), "rb")})
        if res.status_code != 200:
            self.utils.report.error("Klarte ikke generere ACE rapport")
        else:
            self.utils.report.info(
                f"Genererte ACE rapport: {0}", res.json()["url"])

        return True

    @asyncio.coroutine
    async def finalize(self):
        """ 
        Finalize the EPUB.
        """
        self.utils.report.info(
            "Boken er valid. Kopierer til EPUB master-arkiv.")

        archived_path, stored = self.utils.filesystem.storeBook(
            self.epub_fixed.asDir(), self.epub.identifier())
        self.utils.report.attachment(None, archived_path, "DEBUG")
        self.utils.report.title = self.title + ": " + \
            self.epub.identifier() + " er valid 👍😄" + self.epubTitle
        self.utils.filesystem.deleteSource()
        return True
