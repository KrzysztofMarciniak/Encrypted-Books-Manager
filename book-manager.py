import sqlcipher3.dbapi2 as sqlite
from getpass import getpass
from abc import ABC, abstractmethod
from typing import List, Optional
import hashlib
import readline
from datetime import datetime

class Book:
    def __init__(self, id: Optional[int] = None, title: Optional[str] = None, 
                 author: Optional[str] = None, status: str = 'unread',
                 created_at: Optional[str] = None, last_modified: Optional[str] = None,
                 started_reading: Optional[str] = None, finished_reading: Optional[str] = None):
        self.id = id
        self.title = title
        self.author = author
        self.status = status
        self.created_at = created_at
        self.last_modified = last_modified
        self.started_reading = started_reading
        self.finished_reading = finished_reading

    def __str__(self) -> str:
        return f"{self.id:<5} {self.title:<30} {self.author:<20} {self.status:<10} {self.started_reading or 'Not started':<15} {self.finished_reading or 'Not finished':<15}"

    def mark_as_read(self) -> None:
        self.status = 'read'
        self.finished_reading = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class DatabaseManager(ABC):
    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def execute_query(self, query: str, params: tuple = ()) -> None:
        pass

    @abstractmethod
    def fetch_all(self, query: str, params: tuple = ()) -> List[tuple]:
        pass

class DatabaseConnection(DatabaseManager):
    def __init__(self, db_name: str, password: Optional[str] = None):
        self.db_name = db_name
        self.password = password or getpass("Enter database password: ")
        self.conn = None
        self.cursor = None
        self.initial_hash = self._calculate_db_hash()
        self.connect()

    def _calculate_db_hash(self) -> str:
        try:
            with open(self.db_name, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except FileNotFoundError:
            return ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
            final_hash = self._calculate_db_hash()
            if final_hash != self.initial_hash:
                print(f"Database hash changed from {self.initial_hash} to {final_hash}")
    def connect(self) -> bool:
        try:
            self.conn = sqlite.connect(self.db_name)
            self.cursor = self.conn.cursor()
            self.cursor.execute(f"PRAGMA key='{self.password}'")
            return True
        except sqlite.Error as e:
            raise Exception("Database file is corrupted or incorrect password") from None
    def execute_query(self, query: str, params: tuple = ()) -> None:
        self.cursor.execute(query, params)
        self.conn.commit()

    def fetch_all(self, query: str, params: tuple = ()) -> List[tuple]:
        self.cursor.execute(query, params)
        return self.cursor.fetchall()

class BookRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self._init_database()

    def _init_database(self) -> None:
        self.db_manager.execute_query('''
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT,
                status TEXT CHECK(status IN ('unread', 'read')) DEFAULT 'unread',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_reading TIMESTAMP,
                finished_reading TIMESTAMP
            )
        ''')

    def add(self, book: Book) -> Book:
        self.db_manager.execute_query('''
            INSERT INTO books (title, author, created_at, last_modified, started_reading, finished_reading)
            VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL, NULL)
        ''', (book.title, book.author))
        return book

    def get_all(self, status_filter: Optional[str] = None) -> List[Book]:
        query = "SELECT id, title, author, status, created_at, last_modified, started_reading, finished_reading FROM books"
        params = ()
        if status_filter:
            query += " WHERE status = ?"
            params = (status_filter,)
        
        rows = self.db_manager.fetch_all(query, params)
        return [Book(*row) for row in rows]

    def update_status(self, book_id: int, status: str) -> bool:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if status == 'read':
            self.db_manager.execute_query('''
                UPDATE books
                SET status = ?, last_modified = CURRENT_TIMESTAMP,
                    finished_reading = ?,
                    started_reading = COALESCE(started_reading, ?)
                WHERE id = ?
            ''', (status, current_time, current_time, book_id))
        else:
            self.db_manager.execute_query('''
                UPDATE books
                SET status = ?, last_modified = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, book_id))
        return True

    def update_book(self, book_id: int, title: str, author: str, started_reading: Optional[str] = None, finished_reading: Optional[str] = None) -> bool:
        query = '''
            UPDATE books
            SET title = ?, author = ?, last_modified = CURRENT_TIMESTAMP
        '''
        params = [title, author]
        
        if started_reading:
            query += ", started_reading = ?"
            params.append(started_reading)
        if finished_reading:
            query += ", finished_reading = ?"
            params.append(finished_reading)
            
        query += " WHERE id = ?"
        params.append(book_id)
        
        self.db_manager.execute_query(query, tuple(params))
        return True

    def delete(self, book_id: int) -> bool:
        self.db_manager.execute_query('''
            DELETE FROM books
            WHERE id = ?
        ''', (book_id,))
        return True

class BookManagerUI:
    def __init__(self, book_repository: BookRepository):
        self.book_repository = book_repository

    def display_books(self, books: List[Book]) -> None:
        if not books:
            print("No books found!")
            return
            
        print("\nYour Library:")
        print("{:<5} {:<30} {:<20} {:<10} {:<15} {:<15}".format("ID", "Title", "Author", "Status", "Started", "Finished"))
        print("-" * 100)
        for book in books:
            print(str(book))

    def add_book(self) -> None:
        title = input("Enter book title: ")
        author = input("Enter author: ")
        book = Book(title=title, author=author)
        self.book_repository.add(book)
        print(f"Added '{title}' to your library!")

    def edit_book(self) -> None:
        book_id = input("Enter book ID to edit: ")
        try:
            title = input("Enter new title (or press Enter to skip): ")
            author = input("Enter new author (or press Enter to skip): ")
            status = input("Enter new status (read/unread or press Enter to skip): ")
            started_reading = input("Enter started reading date (YYYY-MM-DD HH:MM:SS or press Enter to skip): ")
            finished_reading = input("Enter finished reading date (YYYY-MM-DD HH:MM:SS or press Enter to skip): ")
            
            books = self.book_repository.get_all()
            book = next((b for b in books if b.id == int(book_id)), None)
            if book:
                new_title = title if title else book.title
                new_author = author if author else book.author
                new_started = started_reading if started_reading else book.started_reading
                new_finished = finished_reading if finished_reading else book.finished_reading
                
                if self.book_repository.update_book(int(book_id), new_title, new_author, new_started, new_finished):
                    if status and status in ['read', 'unread']:
                        self.book_repository.update_status(int(book_id), status)
                    print("Book updated successfully!")
            else:
                print("Book not found!")
        except sqlite.Error as e:
            print(f"Error: {e}")

    def mark_as_read(self) -> None:
        book_id = input("Enter book ID to mark as read: ")
        try:
            self.book_repository.update_status(int(book_id), 'read')
            print("Book marked as read!")
        except sqlite.Error as e:
            print(f"Error: {e}")

    def delete_book(self) -> None:
        book_id = input("Enter book ID to delete: ")
        try:
            if self.book_repository.delete(int(book_id)):
                print("Book deleted successfully!")
        except sqlite.Error as e:
            print(f"Error: {e}")

    def run(self) -> None:
        print("\nBook Manager - Encrypted Local Storage")
        print("Commands: add, list, edit, read, delete, quit")
        
        while True:
            command = input("\n> ").strip().lower()
            
            if command == 'add':
                self.add_book()
            elif command == 'list':
                self.display_books(self.book_repository.get_all())
            elif command == 'edit':
                self.display_books(self.book_repository.get_all())
                self.edit_book()
            elif command == 'read':
                self.display_books(self.book_repository.get_all('unread'))
                self.mark_as_read()
            elif command == 'delete':
                self.display_books(self.book_repository.get_all())
                self.delete_book()
            elif command in ('quit', 'exit'):
                print("Goodbye!")
                break
            else:
                print("Invalid command. Try: add, list, edit, read, delete, quit")

if __name__ == "__main__":
    try:
        db_connection = DatabaseConnection("books.db")
        book_repository = BookRepository(db_connection)
        ui = BookManagerUI(book_repository)
        ui.run()
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
    except sqlite.Error as e:
        print("Database file is corrupted or incorrect password")