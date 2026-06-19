#define F_CPU 7372800UL

#include <avr/io.h>
#include <avr/interrupt.h>
#include <avr/eeprom.h>
#include <util/delay.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>

// ========== DINH NGHIA CHAN ==========
#define BUZZER          PB7
#define LED_DEN         PA1     // Den bao an toan
#define LED_QUAT        PA2     // Chan kich Transistor quat
#define LED_CANH_BAO    PA0     // Den do nhap nhay

#define LM35_ADC        0       // Chan PF0
#define MQ2_ADC         1       // Chan PF1

// ========== EEPROM: MAC DINH 50 VA 40 ==========
uint8_t EEMEM ee_temp_threshold = 50;
uint8_t temp_threshold = 50;

uint8_t EEMEM ee_smoke_threshold = 40;
uint8_t smoke_threshold = 40;

// ========== BIEN DUNG CHO TIMER VA UART ==========
volatile unsigned int tick_10ms = 0;
volatile unsigned char flag_2s = 0;

volatile char uart_buffer[20];
volatile uint8_t uart_index = 0;
volatile uint8_t uart_ready = 0;

// Co trang thai he thong
volatile uint8_t is_alarming = 0;
volatile uint8_t fan_auto_mode = 1; // Mac dinh la Auto
volatile uint8_t python_danger = 0;

// Bien luu du lieu do luong
uint16_t base_adc_smoke = 0;
int display_temp = 0;
int smoke_percent = 0;

// ========== LOGIC AN TOAN CHUAN XAC 100% ==========
void evaluate_safety() {
	uint8_t local_temp_danger = (display_temp >= temp_threshold);
	uint8_t local_gas_danger = (smoke_percent >= smoke_threshold);
	uint8_t local_danger = local_temp_danger || local_gas_danger;

	// Xu ly Coi va Den
	if (local_danger || python_danger) {
		is_alarming = 1;
		PORTA &= ~(1 << LED_DEN);
		PORTB &= ~(1 << BUZZER); // Bat coi
		} else {
		is_alarming = 0;
		PORTA |= (1 << LED_DEN);
		PORTA &= ~(1 << LED_CANH_BAO);
		PORTB |= (1 << BUZZER);  // Tat coi
	}

	// Xu ly Quat Auto chuan yeu cau
	if (fan_auto_mode) {
		if (local_gas_danger) {
			PORTA &= ~(1 << LED_QUAT); // Co khoi: Cuong che TAT
			} else if (local_temp_danger) {
			PORTA |= (1 << LED_QUAT);   // Chay nong: Tu dong BAT
			} else {
			PORTA &= ~(1 << LED_QUAT); // Binh thuong: Tu dong TAT
		}
	}
}

void beep_confirm() {
	if (!is_alarming) {
		PORTB &= ~(1 << BUZZER);
		_delay_ms(50);
		PORTB |= (1 << BUZZER);
	}
}

void uart_init(unsigned int baud) {
	unsigned int ubrr = F_CPU / 16 / baud - 1;
	UBRR0H = (unsigned char)(ubrr >> 8);
	UBRR0L = (unsigned char)ubrr;
	UCSR0B = (1 << TXEN0) | (1 << RXEN0) | (1 << RXCIE0);
	UCSR0C = (1 << UCSZ01) | (1 << UCSZ00);
}

void uart_putchar(char c) {
	while (!(UCSR0A & (1 << UDRE0)));
	UDR0 = c;
}

void uart_puts(char *s) {
	while (*s) uart_putchar(*s++);
}

ISR(USART0_RX_vect) {
	char c = UDR0;
	if(c == '\r' || c == '\n') {
		if (uart_index > 0) {
			uart_buffer[uart_index] = '\0';
			uart_ready = 1;
			uart_index = 0;
		}
		} else {
		if(uart_index < 19) {
			uart_buffer[uart_index++] = c;
		}
	}
}

void adc_init() {
	ADMUX = (1 << REFS0);
	ADCSRA = (1 << ADEN) | (1 << ADPS2) | (1 << ADPS1);
}

uint16_t adc_read(uint8_t ch) {
	ADMUX = (ADMUX & 0xF8) | (ch & 0x07);
	ADCSRA |= (1 << ADSC);
	while (ADCSRA & (1 << ADSC));
	return ADCW;
}

void timer1_init() {
	TCCR1A = 0x00;
	TCCR1B = 0x00;
	OCR1A = 1151;
	TCCR1B |= (1 << WGM12);
	TIMSK |= (1 << OCIE1A);
	TCCR1B |= (1 << CS11) | (1 << CS10);
}

ISR(TIMER1_COMPA_vect) {
	tick_10ms++;
	if (is_alarming) {
		if (tick_10ms % 25 == 0) PORTA ^= (1 << LED_CANH_BAO);
	}
	if (tick_10ms >= 200) {
		tick_10ms = 0;
		flag_2s = 1;
	}
}

int main(void) {
	char buffer[50];
	DDRB |= (1 << BUZZER);
	DDRA |= (1 << LED_DEN) | (1 << LED_QUAT) | (1 << LED_CANH_BAO);
	PORTA |= (1 << LED_DEN);
	PORTA &= ~((1 << LED_QUAT) | (1 << LED_CANH_BAO));
	PORTB |= (1 << BUZZER);

	temp_threshold = eeprom_read_byte(&ee_temp_threshold);
	if (temp_threshold == 0xFF || temp_threshold == 0) temp_threshold = 50;
	
	smoke_threshold = eeprom_read_byte(&ee_smoke_threshold);
	if (smoke_threshold == 0xFF || smoke_threshold == 0) smoke_threshold = 40;

	uart_init(9600);
	adc_init();
	timer1_init();
	sei();

	uart_puts("He thong da san sang!\r\n");
	uint32_t sum_base_smoke = 0;
	for (int i = 0; i < 20; i++) {
		adc_read(LM35_ADC);
		adc_read(MQ2_ADC);
		sum_base_smoke += adc_read(MQ2_ADC);
		_delay_ms(100);
	}
	base_adc_smoke = sum_base_smoke / 20;

	while (1) {
		if(uart_ready) {
			uart_ready = 0;
			if(uart_buffer[0] == 'T' || uart_buffer[0] == 't') {
				temp_threshold = atoi((char*)&uart_buffer[1]);
				eeprom_update_byte(&ee_temp_threshold, temp_threshold);
				sprintf(buffer, ">> Da dat nguong Nhiet do = %d C\r\n", temp_threshold);
				uart_puts(buffer);
				beep_confirm(); evaluate_safety();
			}
			else if(uart_buffer[0] == 'S' || uart_buffer[0] == 's' || uart_buffer[0] == 'G' || uart_buffer[0] == 'g') {
				smoke_threshold = atoi((char*)&uart_buffer[1]);
				eeprom_update_byte(&ee_smoke_threshold, smoke_threshold);
				sprintf(buffer, ">> Da dat nguong Gas = %d %%\r\n", smoke_threshold);
				uart_puts(buffer);
				beep_confirm(); evaluate_safety();
			}
			else {
				switch(uart_buffer[0]) {
					case 'O':
					case 'o':
					fan_auto_mode = 1;
					uart_puts(">> QUAT: AUTO\r\n");
					beep_confirm(); evaluate_safety();
					break;
					case 'F':
					fan_auto_mode = 0;
					PORTA |= (1 << LED_QUAT);
					uart_puts(">> QUAT: ON\r\n");
					beep_confirm();
					break;
					case 'f':
					fan_auto_mode = 0;
					PORTA &= ~(1 << LED_QUAT);
					uart_puts(">> QUAT: OFF\r\n");
					beep_confirm();
					break;
					case 'A': python_danger = 1; evaluate_safety(); break;
					case 'a': python_danger = 0; evaluate_safety(); break;
				}
			}
		}

		if (flag_2s) {
			flag_2s = 0;
			uint32_t sum_temp = 0, sum_smoke = 0;
			for (int i = 0; i < 100; i++) {
				sum_temp += adc_read(LM35_ADC);
				sum_smoke += adc_read(MQ2_ADC);
				_delay_us(100);
			}
			
			// --- NHIET DO (Khong tru hao do nua) ---
			float temperature = (float)(sum_temp / 100) * 500.0 / 1024.0;
			display_temp = (int)(temperature + 0.5);

			// --- KHi GAS (Khong tru hao do nua) ---
			long adc_diff = (sum_smoke / 100) - base_adc_smoke;
			if (adc_diff < 0) adc_diff = 0;
			
			smoke_percent = (adc_diff * 100L) / 1024L;
			
			if (smoke_percent <= 2) smoke_percent = 0;
			if (smoke_percent > 100) smoke_percent = 100;

			evaluate_safety();
			
			sprintf(buffer, "Nhiet do hien tai: %d.0 C\r\n", display_temp); uart_puts(buffer);
			sprintf(buffer, "Khoi & Gas: %d %%\r\n", smoke_percent); uart_puts(buffer);
		}
	}
}