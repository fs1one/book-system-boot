package com.first.book.controller;

import com.first.book.common.Result;
import com.first.book.entity.Book;
import com.first.book.service.BookService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@Tag(name = "图书管理", description = "图书的增删改查接口")
@SecurityRequirement(name = "BearerAuth")
@RestController
@RequestMapping("/books")
public class BookController {

    private final BookService bookService;

    public BookController(BookService bookService) {
        this.bookService = bookService;
    }

    @Operation(summary = "图书列表", description = "支持按状态和关键词过滤")
    @GetMapping
    public Result<List<Book>> list(@RequestParam(required = false) Integer uid,
                                   @RequestParam(required = false) Integer status,
                                   @RequestParam(required = false) String keyword){

        List<Book> books = bookService.listBooks(uid, status, keyword);

        return Result.success(books);
    }

    @Operation(summary = "图书详情")
    @GetMapping("/{bid}")
    public Result<Book> detail(@Parameter(description = "图书 id") @PathVariable Integer bid){

        Book book = bookService.getBookById(bid);

        return Result.success(book);
    }

    @Operation(summary = "新增图书")
    @PostMapping
    public Result<Book> save(@RequestBody @Validated Book book){

        bookService.saveBook(book);

        return Result.success(book);
    }

    @Operation(summary = "修改图书")
    @PutMapping("/{bid}")
    public Result<Void> update(@PathVariable Integer bid,
                               @RequestBody @Validated Book book){

        book.setBid(bid);
        bookService.updateBook(book);

        return Result.success(null);
    }

    @Operation(summary = "删除图书")
    @DeleteMapping("/{bid}")
    public Result<Void> delete(@PathVariable Integer bid){

        bookService.deleteBook(bid);

        return Result.success(null);
    }
}
