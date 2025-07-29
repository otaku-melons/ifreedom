from Source.Core.Base.Formats.Ranobe import Branch, Chapter, ChaptersTypes
from Source.Core.Base.Parsers.RanobeParser import RanobeParser
from Source.Core.Base.Formats.BaseFormat import Statuses
from Source.Core.Exceptions import TitleNotFound

from datetime import datetime
from time import sleep
from typing import Any

from recognizers_number import recognize_number, Culture
from bs4 import BeautifulSoup
import dateparser

class Parser(RanobeParser):
	"""Парсер."""
	
	#==========================================================================================#
	# >>>>> ПРИВАТНЫЕ МЕТОДЫ <<<<< #
	#==========================================================================================#

	def __CheckChapterType(self, fullname: str, name: str) -> ChaptersTypes | None:
		"""
		Определяет при возможности тип главы.
			fullname – полное название главы;\n
			name – название главы.
		"""

		fullname = fullname.lower()
		name = name.lower()

		#---> afterword
		#==========================================================================================#
		if "послесловие" in name: return ChaptersTypes.afterword

		#---> art
		#==========================================================================================#
		if name.startswith("начальные") and "иллюстрации" in name: return ChaptersTypes.art

		#---> epilogue
		#==========================================================================================#
		if "эпилог" in name: return ChaptersTypes.epilogue

		#---> extra
		#==========================================================================================#
		if name.startswith("дополнительн") and "истори" in name: return ChaptersTypes.extra
		if name.startswith("бонус") and "истори" in name: return ChaptersTypes.extra
		if name.startswith("экстра"): return ChaptersTypes.extra
		if "глава" not in fullname and "том" in fullname: return ChaptersTypes.extra

		#---> glossary
		#==========================================================================================#
		if name.startswith("глоссарий"): return ChaptersTypes.glossary

		#---> prologue
		#==========================================================================================#
		if "пролог" in name: return ChaptersTypes.prologue

		#---> trash
		#==========================================================================================#
		if name.startswith("реквизиты") and "переводчик" in name: return ChaptersTypes.trash
		if name.startswith("примечани") and "переводчик" in name: return ChaptersTypes.trash

		#---> chapter
		#==========================================================================================#
		if "глава" in fullname: return ChaptersTypes.chapter

		return None

	def __CollectUpdates(self, period: int | None = None, pages: int | None = None) -> list[str]:
		"""
		Собирает список обновлений тайтлов по заданным параметрам.
			period – количество часов до текущего момента, составляющее период получения данных;\n
			pages – количество запрашиваемых страниц.
		"""

		Slugs = list()
		period *= 3600
		IsCollected = False
		Page = 1
		Now = datetime.now()

		while not IsCollected:
			Response = self._Requestor.get(f"https://{self._Manifest.site}/vse-knigi/?sort=По+дате+обновления&bpage={Page}")
			
			if Response.status_code == 200:
				Soup = BeautifulSoup(Response.text, "html.parser")
				Books = Soup.find_all("div", {"class": "flexmobrnew"})

				for Book in Books:
					Book: BeautifulSoup
					TimeBlock = Book.find("div", {"class": "time-home"})
					Link = Book.find("div", {"class": "title-home"}).find("a")["href"]
					Slug = Link[27:-1]
					TimeString = TimeBlock.get_text().strip()
					Date = dateparser.parse(TimeString)
					DeltaTime = Now - Date
					
					if DeltaTime.seconds <= period:
						Slugs.append(Slug)

					else:
						IsCollected = True
						break
					
				if not len(Books) or pages and Page == pages: IsCollected = True
				else: sleep(self._Settings.common.delay)
				Page += 1

			else: self._Portals.request_error(Response, "Unable to request catalog.")

		return Slugs
	
	def __Collect(self, filters: str | None = None, pages: int | None = None) -> list[str]:
		"""
		Собирает список тайтлов по заданным параметрам.
			filters – строка из URI каталога, описывающая параметры запроса;\n
			pages – количество запрашиваемых страниц.
		"""

		Slugs = list()
		IsCollected = False
		Page = 1

		while not IsCollected:
			Response = self._Requestor.get(f"https://{self._Manifest.site}/vse-knigi/?{filters}&bpage={Page}")
			
			if Response.status_code == 200:
				self._PrintCollectingStatus(Page)
				Soup = BeautifulSoup(Response.text, "html.parser")
				Books = Soup.find_all("div", {"class": "flexmobrnew"})

				for Book in Books:
					Book: BeautifulSoup
					Link = Book.find("div", {"class": "title-home"}).find("a")["href"]
					Slug = Link[27:-1]
					Slugs.append(Slug)

				if not len(Books) or pages and Page == pages: IsCollected = True
				Page += 1
				sleep(self._Settings.common.delay)

			else: self._Portals.request_error(Response, "Unable to request catalog.")

		return Slugs

	def __GetAgeLimit(self, soup: BeautifulSoup) -> int | None:
		"""
		Возвращает возрастное ограничение.
			soup – спаршенный код страницы.
		"""

		AgeLimit = None
		if soup.find("div", {"class": "r18"}): AgeLimit = 18

		return AgeLimit

	def __GetAnotherNames(self, soup: BeautifulSoup) -> list[str]:
		"""
		Возвращает список альтернативных названий.
			soup – спаршенный код страницы.
		"""

		AnotherNames = list()
		Descriprion = soup.find("span", {"class": "open-desc"})

		if Descriprion:
			Text = Descriprion["onclick"]

		else: 
			Descriprion = soup.find("div", {"class": "descr-ranobe"})
			Text = Descriprion.get_text().strip()

		if "<br>" in Text:
			if " / " in Text or " | " in Text:
				AnotherLine = Text.split("<br>")[0]
				AnotherLine = AnotherLine[53:]
				AnotherNames = AnotherLine.split(" / ")

		return AnotherNames

	def __GetBookMetadata(self, soup: BeautifulSoup, key: str) -> Any:
		"""
		Возвращает значение определённого поля метаданных.
			soup – спаршенный код страницы;\n
			key – ключ поля.
		"""

		Metadata: list[BeautifulSoup] = soup.find_all("div", {"class": "data-ranobe"})
		Value = None

		for Block in Metadata:
			Bold = Block.find("b")

			if key in Bold.get_text():
				ValueBlock = Block.find("div", {"class": "data-value"})
				Value = ValueBlock.get_text().strip()

		if Value == "Не указан": Value = None

		return Value

	def __GetBranches(self, soup: BeautifulSoup):
		"""
		Получает ветви тайтла.
			soup – спаршенный код страницы.
		"""

		BranchID = self._Title.id
		CurrentBranch = Branch(BranchID)
		ChaptersBlocks = soup.find_all("div", {"class": "li-ranobe"})
	
		for Block in ChaptersBlocks:
			Block: BeautifulSoup
			ChapterID = None
			ChapterName = Block.find("a").get_text().strip()
			ChapterFullname = ChapterName
			ChapterVolume = None
			ChapterNumber = None
			ChapterSlug = Block.find("a")["href"].rstrip("/").split("/")[-1]

			try: ChapterID = int(Block.find("input")["value"])
			except: pass

			if ChapterSlug == "podpiska": ChapterSlug = None

			Results = recognize_number(ChapterName, Culture.English)
			Index = 0

			for Result in Results:
				IsBlocked = False

				if Index == 0 and not ChapterVolume and "том" in ChapterName.lower():
					ChapterVolume = Result.resolution["value"]
					IsBlocked = True

				if not IsBlocked and not ChapterNumber and "глава" in ChapterName.lower():
					ChapterNumber = Result.resolution["value"]

				Index += 1

			ChapterName = self.__ReplaceNumberFromChapterName(ChapterName, ChapterVolume)
			ChapterName = self.__ReplaceNumberFromChapterName(ChapterName, ChapterNumber)
			ChapterType = self.__CheckChapterType(ChapterFullname, ChapterName)

			ChapterAction = "subscription"
			try: ChapterAction = Block.find("label")["for"]
			except: pass
			IsChapterPaid = False if ChapterAction.startswith("download") else True

			ChapterObject = Chapter(self._SystemObjects, self._Title)
			ChapterObject.set_id(ChapterID)
			ChapterObject.set_slug(ChapterSlug)
			ChapterObject.set_name(ChapterName)
			ChapterObject.set_volume(ChapterVolume)
			ChapterObject.set_number(ChapterNumber)
			ChapterObject.set_type(ChapterType)
			ChapterObject.set_is_paid(IsChapterPaid)

			CurrentBranch.add_chapter(ChapterObject)

		self._Title.add_branch(CurrentBranch)	

	def __GetCoverLink(self, soup: BeautifulSoup) -> str:
		"""
		Возвращает ссылку
			soup – спаршенный код страницы.
		"""

		RanobeImage = soup.find("div", {"class": "img-ranobe"})
		RanobeImage = RanobeImage.find("img")
		Link = RanobeImage["src"]
		
		return Link

	def __GetDescription(self, soup: BeautifulSoup) -> str:
		"""
		Возвращает описание тайтла.
			soup – спаршенный код страницы.
		"""

		Descriprion = soup.find("span", {"class": "open-desc"})
		Text = None

		if Descriprion:
			Text = Descriprion["onclick"]

		else: 
			Descriprion = soup.find("div", {"class": "descr-ranobe"})
			Text = Descriprion.get_text().strip()

		return Text

	def __GetGenres(self, soup: BeautifulSoup) -> list[str]:
		"""
		Возвращает список жанров.
			soup – спаршенный код страницы.
		"""

		GenresLine = self.__GetBookMetadata(soup, "Жанры")
		Genres = GenresLine.split(", ")
		
		return Genres

	def __GetID(self, soup: BeautifulSoup) -> int:
		"""
		Возвращает ID тайтла.
			soup – спаршенный код страницы.
		"""

		ID = None
		RatingArea = soup.find("div", {"class": "rating-area"})
		StarsLabel = RatingArea.find("label")
		StarsLabelOnclick = StarsLabel["onclick"]
		ID = StarsLabelOnclick.replace("starSend('zvezdy_proizvedenie', 5, ", "").replace(", 0);", "")
		ID = int(ID.split(",")[0])

		return ID

	def __GetName(self, soup: BeautifulSoup) -> str:
		"""
		Возвращает название тайтла.
			soup – спаршенный код страницы.
		"""

		Name = soup.find("h1", {"class": "entry-title ranobe"})
		Name = Name.get_text().rstrip("☣®").strip()

		return Name

	def __GetOriginalLanguage(self, soup: BeautifulSoup) -> str:
		"""
		Возвращает код оригинального языка произведения по стандарту ISO 639-3.
			soup – спаршенный код страницы.
		"""

		Language = self.__GetBookMetadata(soup, "Язык")
		Languages = {
			"Английский": "eng",
			"Китайский": "zho",
			"Корейский": "kor",
			"Японский": "jpn",
			"Не указан": "rus"
		}
		OriginalLanguage = Languages[Language]
		
		return OriginalLanguage

	def __GetParagraphs(self, chapter: Chapter) -> list[str]:
		"""
		Получает список абзацев главы.
			chapter – данные главы.
		"""

		Paragraphs = list()
		Headers = None

		if self._Settings.custom["cookie"] and chapter.is_paid:
			Headers = {"Cookie": self._Settings.custom["cookie"]}

		elif chapter.is_paid:
			self._Portals.chapter_skipped(self._Title, chapter)
			return Paragraphs

		Response = self._Requestor.get(f"https://{self._Manifest.site}/{self._Title.slug}/{chapter.slug}/", headers = Headers)

		if Response.status_code == 200:
			Soup = BeautifulSoup(Response.text, "lxml")
			if not chapter.id: chapter.set_id(int(Soup.find("input", {"name": "pageid"})["value"]))

			if Soup.find("form", {"aria-label": "Контактная форма"}):
				self._Portals.error("Captcha detected.")

			elif Soup.find("div", {"class": "single-notice"}):
				chapter.set_is_paid(True)
				self._Portals.chapter_skipped(self._Title, chapter)

			else:
				Content = Soup.find("div", {"class": "entry-content"})
				ParagraphsBlocks = Content.find_all("p", recursive = False)
				for Block in ParagraphsBlocks: 
					Paragraphs.append(str(Block))

		elif Response.status_code == 404: self._Portals.chapter_not_found(self._Title, chapter)
		else: self._Portals.request_error(Response, "Unable to request chapter.", exception = False)

		return Paragraphs

	def __GetStatus(self, soup: BeautifulSoup) -> Statuses:
		"""
		Возвращает статус произведения.
			soup – спаршенный код страницы.
		"""

		Status = None
		StatusLine = self.__GetBookMetadata(soup, "Статус книги")
		StatusesDeterminations = {
			"Перевод активен": Statuses.ongoing,
			"Перевод приостановлен": Statuses.dropped,
			"Произведение завершено": Statuses.completed,
			"Не указан": None
		}
		Status = StatusesDeterminations[StatusLine]
		
		return Status

	def __ReplaceNumberFromChapterName(self, name: str, number: str) -> str:
		"""
		Удаляет номер главы или тома из названия главы.
			name – название главы;\n
			number – номер.
		"""

		if number:
			Buffer = list()

			Buffer = name.split(number)
			Buffer = Buffer[1:]
			name = number.join(Buffer)
			name = name.strip()

			if name and not name[0].isalpha():
				name = name.lstrip("-.–")

		return name

	#==========================================================================================#
	# >>>>> ПУБЛИЧНЫЕ МЕТОДЫ <<<<< #
	#==========================================================================================#
	
	def amend(self, branch: Branch, chapter: Chapter):
		"""
		Дополняет главу дайными о слайдах.
			branch – данные ветви;\n
			chapter – данные главы.
		"""

		
		if chapter.slug:
			Paragraphs = self.__GetParagraphs(chapter)
			for Paragraph in Paragraphs: chapter.add_paragraph(Paragraph)

		else: self._Portals.chapter_skipped(self._Title, chapter)

	def collect(self, period: int | None = None, filters: str | None = None, pages: int | None = None) -> list[str]:
		"""
		Собирает список тайтлов по заданным параметрам.
			period – количество часов до текущего момента, составляющее период получения данных;\n
			filters – строка, описывающая фильтрацию (подробнее в README.md);\n
			pages – количество запрашиваемых страниц каталога.
		"""

		Slugs: list[str] = self.__Collect(filters, pages) if not period else self.__CollectUpdates(period, pages)

		return Slugs
	
	def parse(self):
		"""Получает основные данные тайтла."""

		Headers = {"Cookie": self._Settings.custom["cookie"]} if self._Settings.custom["cookie"] else None
		Response = self._Requestor.get(f"https://{self._Manifest.site}/ranobe/{self._Title.slug}/", headers = Headers)

		if Response.status_code == 200:
			Soup = BeautifulSoup(Response.text, "html.parser")
			
			self._Title.set_site(self._Manifest.site)
			self._Title.set_id(self.__GetID(Soup))
			self._Title.set_content_language("rus")
			self._Title.set_localized_name(self.__GetName(Soup))
			# Некорректно работает из-за сложного определения.
			# self._Title.set_another_names(self.__GetAnotherNames(Soup))
			self._Title.add_cover(self.__GetCoverLink(Soup))
			self._Title.add_author(self.__GetBookMetadata(Soup, "Автор"))
			self._Title.set_description(self.__GetDescription(Soup))
			self._Title.set_age_limit(self.__GetAgeLimit(Soup))
			self._Title.set_original_language(self.__GetOriginalLanguage(Soup))
			self._Title.set_status(self.__GetStatus(Soup))
			self._Title.set_is_licensed(False)
			self._Title.set_genres(self.__GetGenres(Soup))

			self.__GetBranches(Soup)

		elif Response.status_code == 404: raise TitleNotFound(self._Title)
		else: self._Portals.request_error(Response, "Unable to request title data.")