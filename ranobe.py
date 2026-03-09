from Source.Core.Base.Formats.Ranobe.ChapterHeaderParser import ChapterHeaderParser
from Source.Core.Base.Formats.Ranobe.Elements import Footnote, Image, Paragraph
from Source.Core.Base.Formats.BaseFormat import Cover, Statuses
from Source.Core.Base.Parsers.RanobeParser import RanobeParser
from Source.Core.Base.Formats.Ranobe import Branch, Chapter
from Source.Core.Exceptions import TitleNotFound

from enum import Enum
import re

from bs4 import BeautifulSoup, Tag

#==========================================================================================#
# >>>>> ВСПОМОГАТЕЛЬНЫЕ СТРУКТУРЫ ДАННЫХ <<<<< #
#==========================================================================================#

class MetadataSVG(Enum):
	"""Идентификаторы SVG-иконки поля метаданных."""

	Author = "laurel-wreath"
	OriginalLanguage = "language"
	Status = "chart-infographic"

#==========================================================================================#
# >>>>> ОСНОВНОЙ КЛАСС <<<<< #
#==========================================================================================#

class Parser(RanobeParser):
	"""Парсер."""

	#==========================================================================================#
	# >>>>> ПРИВАТНЫЕ МЕТОДЫ <<<<< #
	#==========================================================================================#
	
	def __GetMetadataмValue(self, soup: BeautifulSoup, key: MetadataSVG) -> str | None:
		"""
		Возвращает значение поля метаданных книги. Определение идёт по SVG-иконке.

		:param soup: HTML код страницы.
		:type soup: BeautifulSoup
		:param key: Идентификатор SVG-иконки поля метаданных.
		:type key: MetadataSVG
		:return: Текст поля.
		:rtype: str | None
		"""

		InfoList = soup.find("div", {"class": "group-book-info-list"})
		Blocks = InfoList.find_all("div", {"class": "book-info-list"})

		for Block in Blocks:
			ClassSVG = Block.find("svg")["class"]
			if ClassSVG[-1] == f"icon-tabler-{key.value}": return Block.get_text().strip()

	def __SplitParagraphsByBreaks(self, soup: BeautifulSoup, paragraph: Tag) -> tuple[Tag]:
		"""
		Разбивает абзацы по вхождению тега `br`.

		:param paragraph: Разбиваемый абзац.
		:type paragraph: Tag
		:param soup: Парсер страницы.
		:type soup: BeautifulSoup
		:return: Последовательность абзацев.
		:rtype: tuple[Tag]
		"""

		if not paragraph.find("br"): return (paragraph,)

		Text = paragraph.decode_contents()
		Parts = tuple(Line.strip() for Line in re.split(r"<br\s*/?>", Text) if Line.strip())

		return tuple(soup.new_tag("p", string = Part, attrs = paragraph.attrs.copy()) for Part in Parts)

	def __UnwrapInnerTags(self, tag: Tag) -> Tag:
		"""
		Если передан тег абзаца, содержащий блок текста или изображение, разворачивает абзац.

		:param tag: Обрабатываемый тег.
		:type tag: Tag
		:return: Обрабатываемый тег или вложенный тег блока текста или изображения.
		:rtype: Tag
		"""

		if tag.name == "p":
			for InnerTagName in ("blockquote", "img", "h3"):
				InnerTag = tag.find(InnerTagName)
				if InnerTag:
					tag = InnerTag
					break

		return tag

	#==========================================================================================#
	# >>>>> ПРИВАТНЫЕ МЕТОДЫ СОЗДАНИЯ ЭЛЕМЕНТОВ ГЛАВ <<<<< #
	#==========================================================================================#

	def __CreateImageElementFromTag(self, tag: Tag, chapter: Chapter) -> Image:
		"""
		Создаёт элемент `Image` из тега изображения.

		:param tag: Тег изображения.
		:type tag: Tag
		:param chapter: Данные главы.
		:type chapter: Chapter
		:return: Элемент страницы.
		:rtype: Image
		"""

		ImageObject = Image(self._SystemObjects, self, chapter)
		ImageObject.parse_image(tag)
		
		return ImageObject
	
	def __CreateParagraphElementFromTag(self, tag: Tag) -> Paragraph | None:
		"""
		Создаёт элемент `Paragraph` из тега абзаца.

		:param tag: Тег абзаца.
		:type tag: Tag
		:return: Элемент страницы или `None` в случае игнорирования абзаца.
		:rtype: Image
		"""

		ParagraphObject = Paragraph(self._SystemObjects)
		for Break in tag.find_all("br"): Break.decompose()
		Text = tag.decode_contents().strip()
		if not Text: return

		ParagraphObject.set_text(Text)
		ParagraphObject.parse_align(tag)
		
		return ParagraphObject

	#==========================================================================================#
	# >>>>> ПРИВАТНЫЕ МЕТОДЫ ЗАПОЛНЕНИЯ СТРУКТУРЫ ТАЙТЛА <<<<< #
	#==========================================================================================#

	def __CheckLicense(self, soup: BeautifulSoup):
		"""
		Определяет, является ли тайтл лицензированным.

		:param soup: HTML код страницы.
		:type soup: BeautifulSoup
		"""

		LitresPreview = soup.find("div", {"class": "litres_fragment_body"})
		self._Title.set_is_licensed(bool(LitresPreview))

	def __GetAuthor(self, soup: BeautifulSoup):
		"""
		Получает автора тайтла.

		:param soup: HTML код страницы.
		:type soup: BeautifulSoup
		"""

		Author = self.__GetMetadataмValue(soup, MetadataSVG.Author)
		if not Author or Author == "Не указан": return
		self._Title.add_author(Author)

	def __GetBranch(self, soup: BeautifulSoup):
		"""
		Получает данные ветви.

		:param soup: HTML код страницы.
		:type soup: BeautifulSoup
		"""

		CurrentBranch = Branch(self._Title.id)
		ChaptersContainer = soup.find("div", {"data-name": "Главы"})
		if not ChaptersContainer: return

		for Block in ChaptersContainer.find_all("div", {"class": "chapterinfo"}):
			ChapterLink = Block.find("a")
			ChapterSlug = ChapterLink["href"].rstrip("/").split("/")[-1]
			ChapterHeaderData = ChapterHeaderParser(ChapterLink.get_text(), self._Title).parse()

			CurrentChapter = Chapter(self._SystemObjects, self._Title)
			CurrentChapter.set_id(int(ChapterLink["data-id"]))
			if ChapterSlug != "podpiska": CurrentChapter.set_slug(ChapterSlug)
			else: CurrentChapter.set_is_paid(True)
			CurrentChapter.set_name(ChapterHeaderData.name)
			CurrentChapter.set_volume(ChapterHeaderData.volume)
			CurrentChapter.set_number(ChapterHeaderData.number)
			CurrentChapter.set_type(ChapterHeaderData.type)
			CurrentBranch.add_chapter(CurrentChapter)

		CurrentBranch.reverse()
		self._Title.add_branch(CurrentBranch)	

	def __GetCover(self, soup: BeautifulSoup):
		"""
		Получает данные обложки.

		:param soup: HTML код страницы
		:type soup: BeautifulSoup
		"""

		RanobeImage = soup.find("div", {"class": "book-but"})
		if not RanobeImage: return
		RanobeImage = RanobeImage.find("img")
		self._Title.add_cover(Cover(self._SystemObjects, self).set_link(RanobeImage["src"]))

	def __GetDescription(self, soup: BeautifulSoup):
		"""
		Получает описание тайтла.

		:param soup: HTML код страницы.
		:type soup: BeautifulSoup
		"""

		Descriprion = soup.find("div", {"data-name": "Описание"})
		Lines = Descriprion.find_all("p", recursive = False)
		Lines = list(Line.decode_contents() for Line in Lines if Line.get_text().strip())
		self._Title.set_description("\n".join(Lines))

	def __GetGenres(self, soup: BeautifulSoup):
		"""
		Получает список жанров.

		:param soup: HTML код страницы.
		:type soup: BeautifulSoup
		"""

		GenresContainer = soup.find("div", {"class": "genreslist"})
		for Link in GenresContainer.find_all("a"): self._Title.add_genre(Link.get_text())

	def __GetID(self, soup: BeautifulSoup) -> int | None:
		"""
		Получает ID тайтла.

		:param soup: HTML код страницы.
		:type soup: BeautifulSoup
		:return: ID тайтла.
		:rtype: int | None
		"""

		LikesBlock = soup.find("div", {"class": "likesblock"})
		if not LikesBlock: return
		OnClick = LikesBlock.get("onclick")
		if not OnClick: return
		ID = OnClick.split(" ")[-1].rstrip(")")
		if not ID.isdigit(): return
		self._Title.set_id(int(ID))

		return self._Title.id

	def __GetName(self, soup: BeautifulSoup):
		"""
		Получает имя тайтла.

		:param soup: HTML код страницы.
		:type soup: BeautifulSoup
		"""

		Name = soup.find("h1")
		if not Name: return
		Name = Name.get_text().rstrip("☣®").strip()
		self._Title.set_localized_name(Name)

	def __GetOriginalLanguage(self, soup: BeautifulSoup):
		"""
		Получает оригинальный язык тайтла.

		:param soup: HTML код страницы.
		:type soup: BeautifulSoup
		"""

		OriginalLanguage = self.__GetMetadataмValue(soup, MetadataSVG.OriginalLanguage)
		Languages = {
			"Английский": "eng",
			"Китайский": "zho",
			"Корейский": "kor",
			"Японский": "jpn",
			"Не указан": "rus"
		}
		OriginalLanguage = Languages[OriginalLanguage]
		self._Title.set_original_language(OriginalLanguage)

	def __GetStatus(self, soup: BeautifulSoup):
		"""
		Получает статус тайтла.

		:param soup: HTML код страницы.
		:type soup: BeautifulSoup
		"""

		Status = self.__GetMetadataмValue(soup, MetadataSVG.Status)
		if not Status: return
		StatusesDeterminations = {
			"Перевод активен": Statuses.ongoing,
			"Перевод приостановлен": Statuses.dropped,
			"Книга завершена": Statuses.completed,
			"Не указан": None
		}
		Status = StatusesDeterminations[Status]
		self._Title.set_status(Status)

	#==========================================================================================#
	# >>>>> ПУБЛИЧНЫЕ МЕТОДЫ <<<<< #
	#==========================================================================================#
	
	def amend(self, branch: Branch, chapter: Chapter):
		"""
		Дополняет главу дайными о слайдах.

		:param branch: Данные ветви.
		:type branch: Branch
		:param chapter: Данные главы.
		:type chapter: Chapter
		"""
		
		if not chapter.slug:
			self._Portals.chapter_skipped(chapter)
			return

		Response = self._Requestor.get(f"https://{self._Manifest.site}/{self._Title.slug}/{chapter.slug}/")
		if not Response.ok: self._Portals.request_error(Response, "Unable load chapter page.")
		
		Soup = BeautifulSoup(Response.text, "html.parser")
		Container = Soup.find("div", {"class": "chapter-content"})
		for AdvBlock in Container.find_all("div", {"class": "pc-adv"}): AdvBlock.decompose()

		for CurrentTag in Container.find_all(("p", "img"), recursive = False):
			CurrentTag = self.__UnwrapInnerTags(CurrentTag)
			Element = None

			match CurrentTag.name:

				case "p":
					for CurrentParagraph in self.__SplitParagraphsByBreaks(Soup, CurrentTag):
						Element = self.__CreateParagraphElementFromTag(CurrentParagraph)

						if Element:
							chapter.add_element(Element)
							Element = None

				case "img": Element = self.__CreateImageElementFromTag(CurrentTag, chapter)

			if Element: chapter.add_element(Element)
	
	def parse(self):
		"""Получает основные данные тайтла."""

		Response = self._Requestor.get(f"https://{self._Manifest.site}/ranobe/{self._Title.slug}/")

		if Response.status_code == 404: raise TitleNotFound(self._Title)
		elif not Response.ok: self._Portals.request_error(Response, "Unable to request title data.")

		Soup = BeautifulSoup(Response.text, "html.parser")

		self._Title.set_content_language("rus")
		self._Title.set_is_licensed(False)
		
		self.__GetID(Soup)
		self.__GetName(Soup)
		self.__GetCover(Soup)
		self.__GetAuthor(Soup)
		self.__GetDescription(Soup)
		self.__GetOriginalLanguage(Soup)
		self.__GetStatus(Soup)
		self.__CheckLicense(Soup)
		self.__GetGenres(Soup)
		self.__GetBranch(Soup)