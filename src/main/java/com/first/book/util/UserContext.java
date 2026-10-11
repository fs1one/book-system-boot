package com.first.book.util;

public class UserContext {

    private static final ThreadLocal<Integer> CURRENT_UID = new ThreadLocal<>();

    public static void set(Integer uid) {
        CURRENT_UID.set(uid);
    }

    public static Integer getUid(){
        return CURRENT_UID.get();
    }

    public static void clear(){
        CURRENT_UID.remove();
    }
}
