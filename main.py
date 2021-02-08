from flask import Flask, render_template, request, redirect
from bs4 import BeautifulSoup
import requests

books_to_scrape_url = 'https://books.toscrape.com/';


def for_each(item_list, callback):
  for idx, item in enumerate(item_list):
    callback(item, idx)

def map(item_list, callback):
  new_list = []
  def map_item(item, idx):
    modified_item = callback(item, idx)
    new_list.append(modified_item)

  for_each(item_list, map_item)

  return new_list

def filter(item_list, predicate):
  filtered_list = []
  def filter_item(item, idx):
    if predicate(item):
      filtered_list.append(item)
  
  for_each(item_list, filter_item)

  return filtered_list

# MAIN APP
app = Flask(
    __name__,
    static_url_path='',
    static_folder='web/static',
    template_folder='web/templates')


genre_list = []
found_books = None
genre_book_cache = {}
search_history = []


@app.route('/')
def index():
    return redirect('/find-books')

@app.route('/clear', methods=['POST'])
def clear():
  global found_books
  found_books = None()

  return redirect('/find-books')

# goes to the main page of the site and grabs all of the genres listed on the left hand side
def get_genre_list():
  books_page = requests.get(books_to_scrape)
  soup = BeautifulSoup(books_page.content, 'html.parser')
  full_genre_list = soup.find(class_='side_categories').ul.li.ul

  # formats the genres to make them easy to use in our index.html
  def get_genres(item, idx):
    genre = item.a.get_text().strip()
    id = genre.lower().replace(' ', '-')
    return {
      name: genre,
      id: f'{id}_{idx + 2}'
    }
  full_genre_list = map(full_genre_list.find_all('li'), get_genres)[0]

  return full_genre_list

# Iterates through every page of the selected genre and grabs all of the books
def generate_book_list(genre):
  current_page = 1
  total_pages = 1
  book_list = []

# requests the page data and returns a count of the total pages and all the books
  def pull_book_page(pageToPull):
    html_page_ext = 'index.html'
    if pageToPull > 1:
      html_page_ext = f'page-{pageToPull}.html'

    url = f'{books_to_scrape_url}catalogue/category/books/{genre}/{html_page_ext}'
    
    books_page = requests.get(url)
    soup = BeautifulSoup(books_page.content, 'html.parser')
    pagination_section = soup.find(class_='pager')
    page_count = 1
    if pagination_section:
      page_count = pagination_section.find(class_='current').get_text().strip().split().pop()

    book_section = soup.find_all(class_='product_pod')
    return {
      'book_list': book_section,
      'total_pages': int(page_count)
    }

  book_page = pull_book_page(current_page)
  book_list.extend(book_page['book_list'])
  current_page += 1
  total_pages = book_page['total_pages']

  while current_page < total_pages:
    book_page = pull_book_page(current_page)
    book_list.extend(book_page['book_list'])
    current_page += 1

  return book_list


def get_star_count(book):
  star_section = book.find(class_='star-rating')
  star_count_section = star_section['class']
  star_count_text = star_count_section[0]

  star_count = 3

  if star_count_text == 'One':
    star_count = 1
  if star_count_text == 'Two':
    star_count = 2
  if star_count_text == 'Three':
    star_count = 3
  if star_count_text == 'Four':
    star_count = 4
  if star_count_text == 'Five':
    star_count = 5

  return star_count

# truncates the titles to whatever max_length is set
def truncate_titles(title, max_length):
  truncated_title = title[max_length:0]
  return f'{truncated_title}...'

# iterates over all books in list and gets the title, price, and unique url for each book
# also creates a truncated title
def parse_book_info(book_list_dict):
  def get_info(book, idx):
    title = book.h3.find('a')['title']
    short_title = truncate_titles(title, 20)
    return {
      'title': title,
      'short_title': short_title,
      'price': book.find(class_='price_color').get_text(),
      'url': book.h3.find('a')['href'],
      'stars': get_star_count(book)
    }
  return map(book_list_dict, get_info)

@app.route('/find-books')
def find_books():
  global genre_list
  global found_books
  genre_list = get_genre_list()
  return render_template('index.html', genre_list=genre_list, found_books=found_books)


@app.route('/search', methods=['GET'])
def search_get():
  return redirect('/find-books')

# sorts books by either price or title
def sort_books(books, sort_dir):
  def price_sort(book):
    return float(book['price'][1:len(book['price'])])

  def title_sort(book):
    return book['title'].lower()

  if sort_dir == 'price-high':
    books.sort(key=price_sort, reverse=True)
  if sort_dir == 'price-low':
    books.sort(key=price_sort)
  if sort_dir == 'title-high':
    books.sort(key=title_sort)
  if sort_dir == 'title-low':
    books.sort(key=title_sort, reverse=True)

  return books;

@app.route('/search', methods=['POST'])
def search():
  global genre_list
  global found_books
  global search_history

  search_text = request.form.get('search-text') 
  search_history.append(search_text)

  # Only go and grab books if there is search text present
  if not search_tex:
    selected_genre = request.form.get('genre-filter')
    sort_direction = request.form.get('sort-type')

    if selected_genre in genre_book_cache:
      full_book_list = genre_book_cache[selected_genre]
    else:
      full_book_list = generate_book_list(selected_genre)
      genre_book_cache[selected_genre] = full_book_list

    book_info = parse_book_info([full_book_list[0]])
    
    # filters the full list of books by the search string
    def only_matching_books(book):
      if search_text.lower() in book['title'].lower():
        return True
      return False

    filtered_books = filter(book_info, only_matching_books)
    found_books = sort_books(filtered_books, 'price-low')

  return redirect('/find-books')

@app.route('/book-info', methods=['POST'])
def more_book_info():
  global found_books
  book_url = request.form.get('book-url')
  url = f'{books_to_scrape_url}catalogue/{book_url[9:len(book_url)]}'

  book_page = requests.get(url)
  soup = BeautifulSoup(book_page.content, 'html.parser')
  book_title = soup.find('h1').get_text()
  book_description = soup.find('article').find('p', recursive=False).get_text()
  
  def add_desc(book, idx):
    if book['title'] == book_title:
      book.description = book_description
    return book

  found_books = map(found_books, add_desc)

  return redirect('/find-books')

@app.route('/search-history', methods=['GET'])
def search_history_fallback():
  return redirect('/find-books')

@app.route('/search-history', methods=['POST'])
def get_search_history():
  global genre_list
  global found_books
  global search
  # returns a list of the past searches the user has made. The list is added to in the search function
  return render_template('index.html', genre_list=genre_list, found_books=found_books, search_history=search)

app.run(host='0.0.0.0', port=8080)
