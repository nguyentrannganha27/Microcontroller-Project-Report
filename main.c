#define F_CPU 7372800UL

#include <avr/io.h>
#include <avr/interrupt.h>
#include <avr/eeprom.h>
#include <util/delay.h>
#include <stdio.h>
#include <math.h>
#include <string.h>
#include <stdlib.h>

// ========== DINH NGHIA CHAN ==========
#define BUZZER          PB7
#define LED_DEN         PA1     // Den bao an toan
#define LED_QUAT        PA2
#define LED_CANH_BAO    PA0     // Den canh bao nhap nhay

#define LM35_ADC        0       // Chan PF0
#define MQ2_ADC         1       // Chan PF1

// ========== EEPROM ==========
uint8_t EEMEM ee_temp_threshold = 50;
uint8_t temp_threshold = 50;
uint8_t smoke_threshold = 60;

// ========== BIEN DUNG CHO TIMER VA UART INTERRUPT ==========
volatile unsigned int tick_10ms = 0;
volatile unsigned char flag_2s = 0;

volatile char uart_buffer[20];
volatile uint8_t uart_index = 0;
volatile uint8_t uart_ready = 0;

// Co bao dong
volatile uint8_t is_alarming = 0;
volatile uint8_t fan_auto_mode = 0;

// ============================================
// BIEN LUU MUC NEN KHI GAS (AUTO-CALIBRATION)
// ============================================
uint16_t base_adc_smoke = 0;

// ========== UART0 ==========
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
	while (*s) {
		uart_putchar(*s++);
	}
}

// ========== UART RECEIVE INTERRUPT ==========
ISR(USART0_RX_vect)
{
	char c = UDR0;

	if(c == '\r' || c == '\n')
	{
		uart_buffer[uart_index] = '\0';
		uart_ready = 1;
		uart_index = 0;
	}
	else
	{
		if(uart_index < 19)
		{
			uart_buffer[uart_index++] = c;
		}
	}
}

// ========== ADC ==========
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

// ========== TIMER1 ==========
void timer1_init() {
	TCCR1A = 0x00;
	TCCR1B = 0x00;

	OCR1A = 1151;   // Ngat moi 10ms voi F_CPU = 7.3728MHz, prescaler 64

	TCCR1B |= (1 << WGM12);
	TIMSK |= (1 << OCIE1A);
	TCCR1B |= (1 << CS11) | (1 << CS10);
}

ISR(TIMER1_COMPA_vect) {
	tick_10ms++;

	// Neu dang bao dong thi PA0 nhap nhay moi 250ms
	if (is_alarming) {
		if (tick_10ms % 25 == 0) {
			PORTA ^= (1 << LED_CANH_BAO);
		}
	}

	// Tao co moi 2 giay gui data
	if (tick_10ms >= 200) {
		tick_10ms = 0;
		flag_2s = 1;
	}
}

// ========== MAIN ==========
int main(void) {
	char buffer[50];

	float temperature;
	int display_temp;
	int smoke_percent;
	char cmd;

	// ===== PORT OUTPUT =====
	DDRB |= (1 << BUZZER);
	DDRA |= (1 << LED_DEN) | (1 << LED_QUAT) | (1 << LED_CANH_BAO);

	// ===== TRANG THAI BAN DAU =====
	PORTA |= (1 << LED_DEN);
	PORTA &= ~((1 << LED_QUAT) | (1 << LED_CANH_BAO));
	PORTB |= (1 << BUZZER);

	// ===== DOC EEPROM =====
	temp_threshold = eeprom_read_byte(&ee_temp_threshold);
	if (temp_threshold == 0xFF || temp_threshold == 0) {
		temp_threshold = 35;
	}

	// ===== INIT =====
	uart_init(9600);
	adc_init();
	timer1_init();
	sei();

	// =======================================================
	// QUA TRINH KHOI DONG VA HOC MUC NEN (AUTO-ZERO CALIB)
	// =======================================================
	uart_puts("Dang khoi dong va hieu chuan moi truong...\r\n");
	
	uint32_t sum_base_smoke = 0;
	for (int i = 0; i < 20; i++) {
		adc_read(LM35_ADC); // Dummy read
		
		adc_read(MQ2_ADC);  // Dummy read
		sum_base_smoke += adc_read(MQ2_ADC);
		
		_delay_ms(100);
	}
	base_adc_smoke = sum_base_smoke / 20; // Chot muc nen moi truong hien tai
	
	uart_puts("He thong chong chay da san sang!\r\n");

	while (1) {
		// ========================================================
		// 1. XU LY LENH UART TU PYTHON (SLAVE MODE)
		// ========================================================
		if(uart_ready)
		{
			uart_ready = 0;

			// Xem nguong hien tai
			if(strcmp((char*)uart_buffer,"R")==0)
			{
				sprintf(buffer, 
				"Temp=%d C, Smoke=%d %%\r\n", 
				temp_threshold, smoke_threshold);

				uart_puts(buffer);
			}
			
			// Dat nhiet do
			else if(uart_buffer[0]=='T')
			{
				temp_threshold = atoi((char*)&uart_buffer[1]);

				eeprom_write_byte(&ee_temp_threshold, temp_threshold);

				sprintf(buffer, 
				"Da dat nguong nhiet do = %d C\r\n", 
				temp_threshold);

				uart_puts(buffer);
			}

			// Dat khoi
			else if(uart_buffer[0]=='S')
			{
				smoke_threshold = atoi((char*)&uart_buffer[1]);

				sprintf(buffer, 
				"Da dat nguong khoi = %d %%\r\n", 
				smoke_threshold);

				uart_puts(buffer);
			}

			else
			{
				cmd = uart_buffer[0];

				switch(cmd)
				{
				case 'O':
				fan_auto_mode = 1;
				uart_puts("FAN AUTO MODE\r\n");
				break;

				case 'M':
				fan_auto_mode = 0;
				uart_puts("FAN MANUAL MODE\r\n");
				break;
				
				case 'L':
				uart_puts("PA1 la den bao an toan, khong dieu khien tay.\r\n");
				break;

				case 'l':
				uart_puts("PA1 la den bao an toan, khong dieu khien tay.\r\n");
				break;

				case 'F':  // Bat quat
				PORTA |= (1 << LED_QUAT);
				uart_puts("QUAT: ON\r\n");
				if (!is_alarming) {
					PORTB &= ~(1 << BUZZER);
					_delay_ms(50);
					PORTB |= (1 << BUZZER);
				}
				break;

				case 'f':  // Tat quat
				PORTA &= ~(1 << LED_QUAT);
				uart_puts("QUAT: OFF\r\n");
				if (!is_alarming) {
					PORTB &= ~(1 << BUZZER);
					_delay_ms(50);
					PORTB |= (1 << BUZZER);
				}
				break;

				case 'A':  // Bat bao dong
				is_alarming = 1;
				PORTA &= ~(1 << LED_DEN);
				PORTB &= ~(1 << BUZZER);
				uart_puts("CANH BAO: KICH HOAT!\r\n");
				break;

				case 'a':  // Tat bao dong
				is_alarming = 0;
				PORTA |= (1 << LED_DEN);
				PORTA &= ~(1 << LED_CANH_BAO);
				PORTB |= (1 << BUZZER);
				uart_puts("CANH BAO: AN TOAN!\r\n");
				break;
			}
		}
		}

		// ========================================================
		// 2. MOI 2 GIAY DOC VA GUI DU LIEU 1 LAN
		// ========================================================
		if (flag_2s) {
			flag_2s = 0;

			// --- BO LOC TRUNG BINH CONG (CHONG NHIEU) ---
			uint32_t sum_temp = 0;
			uint32_t sum_smoke = 0;

			for (int i = 0; i < 100; i++) {
				adc_read(LM35_ADC);
				sum_temp += adc_read(LM35_ADC);

				adc_read(MQ2_ADC);
				sum_smoke += adc_read(MQ2_ADC);

				_delay_us(100);
			}

			uint16_t avg_adc_temp = sum_temp / 100;
			uint16_t avg_adc_smoke = sum_smoke / 100;

			// --- TINH TOAN NHIET DO ---
			temperature = (float)avg_adc_temp * 500.0 / 1024.0;
			display_temp = (int)(temperature + 0.5);

			// ====================================================
			// --- THUAT TOAN TINH KHI GAS (DO NHAY CAO) ---
			// ====================================================
			smoke_percent = (avg_adc_smoke * 100UL) / 1023UL;
			// ===== BAO DONG NHIET DO =====
			if(display_temp >= temp_threshold)
			{
				is_alarming = 1;

				PORTA &= ~(1 << LED_DEN);

				// Chi tu bat quat khi AUTO
				if(fan_auto_mode)
				{
					PORTA |= (1 << LED_QUAT);
				}

				PORTB &= ~(1 << BUZZER);
			}

			// ===== BAO DONG KHOI =====
			else if(smoke_percent >= smoke_threshold)
			{
				is_alarming = 1;

				PORTA &= ~(1 << LED_DEN);      // Tat den xanh

				PORTA &= ~(1 << LED_QUAT);     // Tat quat

				PORTB &= ~(1 << BUZZER);       // Bat coi
			}

			// ===== AN TOAN =====
			else
			{
				is_alarming = 0;

				PORTA |= (1 << LED_DEN);       // Den xanh

				if(fan_auto_mode)
				{
					PORTA &= ~(1 << LED_QUAT);
				}    // Tat quat
				PORTA &= ~(1 << LED_CANH_BAO);

				PORTB |= (1 << BUZZER);        // Tat coi
			}

			// --- GUI LEN PYTHON ---
			sprintf(buffer, "Nhiet do hien tai: %d.0 C\r\n", display_temp);
			uart_puts(buffer);

			sprintf(buffer, "KHOI: %d %%\r\n", smoke_percent);
			uart_puts(buffer);
		}
	}
}
