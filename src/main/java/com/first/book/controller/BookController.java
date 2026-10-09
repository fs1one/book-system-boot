package com.first.book.controller;

import com.first.book.common.Result;
import com.first.book.entity.Book;
import com.first.book.service.BookService;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/book")
public class BookController {

    private final BookService bookService;

    public BookController(BookService bookService) {
        this.bookService = bookService;
    }

    @GetMapping("/list")
    public Result<List<Book>> list(@RequestParam(required = false) Integer uid,
                                   @RequestParam(required = false) Integer status,
                                   @RequestParam(required = false) String keyword){

        List<Book> books = bookService.listBooks(uid, status, keyword);

        return Result.success(books);
    }

    @PostMapping("/save")
    public Result<Void> save(@RequestBody @Validated Book book){

        bookService.saveBook(book);

        return Result.success(null);
    }
}
