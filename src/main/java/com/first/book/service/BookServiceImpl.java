package com.first.book.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.first.book.entity.Book;
import com.first.book.exception.BizException;
import com.first.book.mapper.BookMapper;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class  BookServiceImpl implements BookService{

    private final BookMapper bookMapper;

    public BookServiceImpl(BookMapper bookMapper) {
        this.bookMapper = bookMapper;
    }

    @Override
    public List<Book> listBooks(Integer uid, Integer status, String keyword) {

        if(uid != null && uid < 0){
            throw new BizException("uid 不能为负数");
        }

        QueryWrapper<Book> qw = new QueryWrapper<>();

        if(uid != null){
            qw.eq("uid", uid);
        }

        if(status != null){
            qw.eq("status", status);
        }

        if(keyword != null && !keyword.isBlank()){
            qw.like("title", keyword);
        }

        qw.orderByDesc("bid");

        return bookMapper.selectList(qw);
    }
}
