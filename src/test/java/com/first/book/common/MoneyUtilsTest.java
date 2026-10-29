package com.first.book.common;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

/**
 * 金额工具类的验收测试：由 DSH 侧先行冻结，产出方不得修改。
 */
class MoneyUtilsTest {

    @Test
    void toCents_roundsHalfUp_inDecimal() {
        assertEquals(4550L, MoneyUtils.toCents(45.50));
        assertEquals(4551L, MoneyUtils.toCents(45.505));
        assertEquals(4550L, MoneyUtils.toCents(45.4999));
    }

    @Test
    void toCents_absorbsBinaryFloatingNoise() {
        assertEquals(30L, MoneyUtils.toCents(0.1 + 0.2));
        assertEquals(100L, MoneyUtils.toCents(1.0));
    }

    @Test
    void toCents_rejectsInvalidInput() {
        assertThrows(IllegalArgumentException.class, () -> MoneyUtils.toCents(null));
        assertThrows(IllegalArgumentException.class, () -> MoneyUtils.toCents(Double.NaN));
        assertThrows(IllegalArgumentException.class, () -> MoneyUtils.toCents(Double.POSITIVE_INFINITY));
        assertThrows(IllegalArgumentException.class, () -> MoneyUtils.toCents(-1.0));
    }

    @Test
    void toYuan_roundTrips() {
        assertEquals(45.5, MoneyUtils.toYuan(4550L), 1e-9);
        assertEquals(0.3, MoneyUtils.toYuan(30L), 1e-9);
    }

    @Test
    void format_usesTwoDecimals_andLeadingSign() {
        assertEquals("¥45.50", MoneyUtils.format(4550L));
        assertEquals("-¥45.50", MoneyUtils.format(-4550L));
        assertEquals("¥0.00", MoneyUtils.format(0L));
    }

    @Test
    void normalizePrice_goesThroughCents() {
        assertEquals(45.5, MoneyUtils.normalizePrice(45.4999), 1e-9);
        assertEquals(0.3, MoneyUtils.normalizePrice(0.1 + 0.2), 1e-9);
    }
}
