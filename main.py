from Source.Core.Base.SourceOperator import BaseSourceOperator

from datetime import datetime
from time import sleep

from bs4 import BeautifulSoup
import dateparser

class SourceOperator(BaseSourceOperator):
	"""Оператор источника."""

	#==========================================================================================#
	# >>>>> ПРИВАТНЫЕ МЕТОДЫ КОЛЛЕКЦИОНИРОВАНИЯ <<<<< #
	#==========================================================================================#

	def __Collect(self, filters: str | None = None, pages: int | None = None) -> tuple[str]:
		"""
		Собирает список тайтлов по заданным параметрам.

		:param filters: Строка из URI каталога, описывающая параметры запроса.
		:type filters: str | None
		:param pages: Количество запрашиваемых страниц.
		:type pages: int | None
		:raises ParsingError: Выбрасывается при ошибке коллекционирования.
		:return: Набор алиасов собранных тайтлов.
		:rtype: tuple[str]
		"""

		Slugs = list()
		IsCollected = False
		Page = 1

		while not IsCollected:
			Response = self._Requestor.get(f"https://{self._Manifest.site}/vse-knigi/?{filters}&bpage={Page}")
			
			if Response.status_code == 200:
				
				Soup = BeautifulSoup(Response.text, "html.parser")
				Books = Soup.find_all("div", {"class": "flexmobrnew"})

				for Book in Books:
					Book: BeautifulSoup
					Link = Book.find("div", {"class": "title-home"}).find("a")["href"]
					Slug = Link[27:-1]
					Slugs.append(Slug)

				if not len(Books) or pages and Page == pages: IsCollected = True
				Page += 1
				self._Portals.collect_progress_by_page(Page)
				sleep(self._Settings.common.delay)

			else: self._Portals.request_error(Response, "Unable to request catalog.")

		return tuple(Slugs)

	def __CollectUpdates(self, period: int | None = None, pages: int | None = None) -> tuple[str]:
		"""
		Собирает алиасы тайтлов, обновлённых за указанный период времени (в часах).

		:param period: Количество часов до текущего момента, составляющее период получения данных.
		:type period: int
		:param pages: Количество запрашиваемых страниц.
		:type pages: int | None
		:return: Последовательность алиасов тайтлов.
		:rtype: tuple[str]
		:raises ParsingError: Выбрасывается при ошибке получения обновлений.
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

		return tuple(Slugs)
	
	#==========================================================================================#
	# >>>>> ПУБЛИЧНЫЕ МЕТОДЫ <<<<< #
	#==========================================================================================#

	def collect(self, period: int | None = None, filters: str | None = None, pages: int | None = None) -> tuple[str]:
		"""
		Собирает список алиасов тайтлов по заданным параметрам.

		:param period: Количество часов до текущего момента, составляющее период получения данных.
		:type period: int | None
		:param filters: Строка, описывающая фильтрацию (подробнее в README.md парсера).
		:type filters: str | None
		:param pages: Количество запрашиваемых страниц каталога.
		:type pages: int | None
		:return: Набор собранных алиасов.
		:rtype: tuple[str]
		"""

		Slugs = self.__Collect(filters, pages) if not period else self.__CollectUpdates(period, pages)

		return Slugs