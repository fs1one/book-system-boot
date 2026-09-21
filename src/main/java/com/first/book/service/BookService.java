package com.first.book.service;

import com.first.book.entity.Book;

import java.util.List;

public interface BookService {

    List<Book> listBooks(Integer uid, Integer status, String keyword);
}
