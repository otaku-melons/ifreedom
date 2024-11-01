from Source.Core.Formats.Ranobe import Branch, Chapter, Ranobe, Statuses
from Source.Core.ImagesDownloader import ImagesDownloader
from Source.Core.Base.RanobeParser import RanobeParser
from Source.Core.Exceptions import TitleNotFound

from dublib.WebRequestor import Protocols, WebConfig, WebLibs, WebRequestor
from dublib.Methods.Data import RemoveRecurringSubstrings, Zerotify
from datetime import datetime
from dublib.Polyglot import HTML
from bs4 import BeautifulSoup
from time import sleep

import dateparser
import hashlib

#==========================================================================================#
# >>>>> ОПРЕДЕЛЕНИЯ <<<<< #
#==========================================================================================#

VERSION = "0.1.0"
NAME = "ifreedom"
SITE = "ifreedom.su"
TYPE = Ranobe

#==========================================================================================#
# >>>>> ОСНОВНОЙ КЛАСС <<<<< #
#==========================================================================================#

class Parser(RanobeParser):
	"""Парсер."""

	#==========================================================================================#
	# >>>>> ПЕРЕОПРЕДЕЛЯЕМЫЕ МЕТОДЫ <<<<< #
	#==========================================================================================#

	def _InitializeRequestor(self) -> WebRequestor:
		"""Инициализирует модуль WEB-запросов."""

		Config = WebConfig()
		Config.select_lib(WebLibs.requests)
		Config.generate_user_agent()
		Config.set_retries_count(self._Settings.common.retries)
		Config.add_header("Referer", f"https://{SITE}/")
		WebRequestorObject = WebRequestor(Config)

		if self._Settings.proxy.enable: WebRequestorObject.add_proxy(
			Protocols.HTTPS,
			host = self._Settings.proxy.host,
			port = self._Settings.proxy.port,
			login = self._Settings.proxy.login,
			password = self._Settings.proxy.password
		)

		return WebRequestorObject
	
	#==========================================================================================#
	# >>>>> ПРИВАТНЫЕ МЕТОДЫ <<<<< #
	#==========================================================================================#

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
			Response = self._Requestor.get(f"https://{SITE}/vse-knigi/?sort=По+дате+обновления&bpage={Page}")
			
			if Response.status_code == 200:
				self._PrintCollectingStatus(Page)
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
				if IsCollected: self._SystemObjects.logger.titles_collected(len(Slugs))
				Page += 1
				sleep(self._Settings.common.delay)

			else: self._SystemObjects.logger.request_error(Response, "Unable to request catalog.")

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
			Response = self._Requestor.get(f"https://{SITE}/vse-knigi/?{filters}&bpage={Page}")
			
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
				if IsCollected: self._SystemObjects.logger.titles_collected(len(Slugs))
				Page += 1
				sleep(self._Settings.common.delay)

			else: self._SystemObjects.logger.request_error(Response, "Unable to request catalog.")

		return Slugs

	def __GetCoverLink(self, soup: BeautifulSoup) -> str:
		"""
		Возвращает ссылку
			soup – спаршенный код страницы.
		"""

		RanobeImage = soup.find("div", {"class": "img-ranobe"})
		RanobeImage = RanobeImage.find("img")
		Link = RanobeImage["src"]
		
		return Link

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
		ID = int(ID)

		return ID

	def __GetName(self, soup: BeautifulSoup) -> str:
		"""
		Возвращает название тайтла.
			soup – спаршенный код страницы.
		"""

		Name = soup.find("h1", {"class": "entry-title ranobe"})
		Name = Name.get_text().rstrip("☣").strip()

		return Name

	#==========================================================================================#
	# >>>>> ПУБЛИЧНЫЕ МЕТОДЫ <<<<< #
	#==========================================================================================#
	
	def amend(self, branch: Branch, chapter: Chapter):
		"""
		Дополняет главу дайными о слайдах.
			branch – данные ветви;\n
			chapter – данные главы.
		"""

		# Paragraphs = self.__GetParagraphs(chapter)
		# for Paragraph in Paragraphs: chapter.add_paragraph(Paragraph)

	def collect(self, period: int | None = None, filters: str | None = None, pages: int | None = None) -> list[str]:
		"""
		Собирает список тайтлов по заданным параметрам.
			period – количество часов до текущего момента, составляющее период получения данных;\n
			filters – строка, описывающая фильтрацию (подробнее в README.md);\n
			pages – количество запрашиваемых страниц каталога.
		"""

		if filters and not period:
			self._SystemObjects.logger.collect_filters(filters)

		elif filters and period:
			self._SystemObjects.logger.collect_filters_ignored()
			self._SystemObjects.logger.collect_period(period)

		if pages:
			self._SystemObjects.logger.collect_pages(pages)

		Slugs: list[str] = self.__Collect(filters, pages) if not period else self.__CollectUpdates(period, pages)

		return Slugs
	
	def parse(self):
		"""Получает основные данные тайтла."""

		Response = self._Requestor.get(f"https://{SITE}/ranobe/{self._Title.slug}/")

		if Response.status_code == 200:
			Soup = BeautifulSoup(Response.text, "html.parser")
			
			self._Title.set_site(SITE)
			self._Title.set_id(self.__GetID(Soup))
			self._Logger.parsing_start(self._Title)
			self._Title.set_content_language("rus")
			self._Title.set_localized_name(self.__GetName(Soup))
			# self._Title.set_eng_name(None)
			# self._Title.set_another_names([])
			self._Title.add_cover(self.__GetCoverLink(Soup))
			# self._Title.set_publication_year(Data["issue_year"])
			# self._Title.set_description(self.__GetDescription(Data))
			# self._Title.set_age_limit(self.__GetAgeLimit(Data))
			# self._Title.set_original_language(self.__GetOriginalLanguage(Data))
			# self._Title.set_status(self.__GetStatus(Data))
			# self._Title.set_is_licensed(Data["is_licensed"])
			# self._Title.set_genres(self.__GetGenres(Data))
			# self._Title.set_tags(self.__GetTags(Data))
			
			# self.__GetBranches(Data)
			pass

		elif Response.status_code == 404: raise TitleNotFound(self._Title)
		else: self._SystemObjects.logger.request_error(Response, "Unable to request title data.")