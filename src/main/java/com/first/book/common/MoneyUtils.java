package com.first.book.common;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * 金额工具类：负责「元」与「分」之间的换算。
 *
 * <p>所有换算都走 {@link BigDecimal}，避免 double 二进制误差导致的精度漂移
 * （例如 0.1 + 0.2 == 0.30000000000000004）。</p>
 */
public final class MoneyUtils {

    private static final BigDecimal HUNDRED = BigDecimal.valueOf(100);
    private static final String CURRENCY_SYMBOL = "¥";

    private MoneyUtils() {
    }

    /**
     * 元转分，按十进制四舍五入到分（HALF_UP）。
     *
     * @param yuan 金额（元），不能为 null / NaN / 无穷 / 负数
     * @return 金额（分）
     * @throws IllegalArgumentException 入参非法时抛出，异常信息中包含原值
     */
    public static long toCents(Double yuan) {
        if (yuan == null) {
            throw new IllegalArgumentException("金额不能为 null");
        }

        if (yuan.isNaN() || yuan.isInfinite()) {
            throw new IllegalArgumentException("金额必须是有限数字: " + yuan);
        }

        if (yuan < 0) {
            throw new IllegalArgumentException("金额不能为负数: " + yuan);
        }

        return BigDecimal.valueOf(yuan)
                .multiply(HUNDRED)
                .setScale(0, RoundingMode.HALF_UP)
                .longValueExact();
    }

    /**
     * 分转元，与 {@link #toCents(Double)} 互为逆运算。
     *
     * @param cents 金额（分）
     * @return 金额（元）
     */
    public static double toYuan(long cents) {
        return BigDecimal.valueOf(cents)
                .movePointLeft(2)
                .doubleValue();
    }

    /**
     * 格式化金额（分），两位小数并带货币符号，负号位于货币符号之前。
     *
     * <p>示例：4550 → ¥45.50，-4550 → -¥45.50，0 → ¥0.00</p>
     *
     * @param cents 金额（分）
     * @return 格式化后的金额文本
     */
    public static String format(long cents) {
        BigDecimal yuan = BigDecimal.valueOf(cents).movePointLeft(2);
        String sign = yuan.signum() < 0 ? "-" : "";
        return sign + CURRENCY_SYMBOL + yuan.abs().setScale(2, RoundingMode.UNNECESSARY).toPlainString();
    }

    /**
     * 归一化价格：等价于 {@code toYuan(toCents(yuan))}，即先四舍五入到分再转回元。
     *
     * @param yuan 金额（元）
     * @return 归一化后的金额（元）
     * @throws IllegalArgumentException 入参非法时抛出（见 {@link #toCents(Double)}）
     */
    public static Double normalizePrice(Double yuan) {
        return toYuan(toCents(yuan));
    }
}
