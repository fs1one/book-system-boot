package com.first.book.controller;

import com.first.book.entity.Book;
import com.first.book.mapper.BookMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/book")
public class BookController {

    @Autowired
    private BookMapper bookMapper;

    @GetMapping("/list")
    public List<Book> list(){
        return bookMapper.selectList(null);
    }

}
