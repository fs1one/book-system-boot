package com.first.book.service;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.first.book.common.MoneyUtils;
import com.first.book.entity.Book;
import com.first.book.exception.BizException;
import com.first.book.mapper.BookMapper;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class  BookServiceImpl implements BookService{

    private final BookMapper bookMapper;

    public BookServiceImpl(BookMapper bookMapper) {
        this.bookMapper = bookMapper;
    }

    @Cacheable(value = "bookList", key = "#uid + ':' + #status + ':' + #keyword")
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

    @CacheEvict(value = "bookList", allEntries = true)
    @Override
    public void saveBook(Book book){

        normalizePriceOf(book);

        int rows = bookMapper.insert(book);

        if(rows == 0){
            throw new BizException("保存失败");
        }
    }

    @Override
    public Book getBookById(Integer bid) {

        Book book = bookMapper.selectById(bid);

        if(book == null){
            throw new BizException("图书不存在");
        }

        return book;
    }

    @CacheEvict(value = "bookList", allEntries = true)
    @Override
    public void updateBook(Book book){

        Book exist = bookMapper.selectById(book.getBid());

        if(exist == null){
            throw new BizException("图书不存在");
        }

        normalizePriceOf(book);

        bookMapper.updateById(book);
    }

    /**
     * 价格归一化到「分」的精度；null 保持原样，交给 Book 上的 @NotNull 校验。
     */
    private void normalizePriceOf(Book book) {

        if(book == null || book.getPrice() == null){
            return;
        }

        book.setPrice(MoneyUtils.normalizePrice(book.getPrice()));
    }

    @CacheEvict(value = "bookList", allEntries = true)
    @Override
    public void deleteBook(Integer bid){

        int rows = bookMapper.deleteById(bid);

        if(rows == 0){
            throw new BizException("图书不存在");
        }
    }
}
