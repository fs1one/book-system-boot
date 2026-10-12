package com.first.book.controller;

import com.first.book.common.Result;
import com.first.book.entity.Book;
import com.first.book.service.BookService;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/books")
public class BookController {

    private final BookService bookService;

    public BookController(BookService bookService) {
        this.bookService = bookService;
    }

    @GetMapping
    public Result<List<Book>> list(@RequestParam(required = false) Integer uid,
                                   @RequestParam(required = false) Integer status,
                                   @RequestParam(required = false) String keyword){

        List<Book> books = bookService.listBooks(uid, status, keyword);

        return Result.success(books);
    }

    @GetMapping("/{bid}")
    public Result<Book> detail(@PathVariable Integer bid){

        Book book = bookService.getBookById(bid);

        return Result.success(book);
    }

    @PostMapping
    public Result<Book> save(@RequestBody @Validated Book book){

        bookService.saveBook(book);

        return Result.success(book);
    }

    @PutMapping("/{bid}")
    public Result<Void> update(@PathVariable Integer bid,
                               @RequestBody @Validated Book book){

        book.setBid(bid);
        bookService.updateBook(book);

        return Result.success(null);
    }

    @DeleteMapping("/{bid}")
    public Result<Void> delete(@PathVariable Integer bid){

        bookService.deleteBook(bid);

        return Result.success(null);
    }
}
