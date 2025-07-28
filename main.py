import sys
import sqlite3
import csv
import os
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QDateEdit, QComboBox, QLabel, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget, QDialog,
    QDialogButtonBox, QMessageBox, QFormLayout, QGroupBox, QFrame,
    QListWidget, QListWidgetItem, QStatusBar, QToolBar, QFileDialog
)
from PySide6.QtCore import Qt, QDate, QSize, QSettings
from PySide6.QtGui import QFont, QIcon, QColor, QPainter, QAction
from PySide6.QtCharts import QChart, QChartView, QPieSeries

# --- CONSTANTES E ESTILO GLOBAL ---
DB_FILENAME = 'lcdpr.db'
APP_ICON = 'agro_icon.png'
STYLE_SHEET = """
QMainWindow {
    background-color: #000000;
}
QWidget {
    font-family: 'Segoe UI', Arial, sans-serif;
    color: white;
    background-color: #000000;
}
QLineEdit, QDateEdit, QComboBox, QTextEdit {
    color: #2c3e50;
    background-color: white;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    padding: 6px;
}
QLineEdit::placeholder {
    color: #7f8c8d;
}
QPushButton {
    background-color: #3498db;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
    min-height: 30px;
}
QPushButton:hover { background-color: #2980b9; }
QPushButton:pressed { background-color: #1c6ea4; }
QPushButton#danger { background-color: #e74c3c; }
QPushButton#danger:hover { background-color: #c0392b; }
QPushButton#success { background-color: #2ecc71; }
QPushButton#success:hover { background-color: #27ae60; }
QGroupBox {
    border: 1px solid #bdc3c7;
    border-radius: 6px;
    margin-top: 10px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QTableWidget {
    background-color: white;
    color: #2c3e50;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    gridline-color: #ecf0f1;
    alternate-background-color: #f8f9fa;
}
QHeaderView::section {
    background-color: #3498db;
    color: white;
    padding: 6px;
    border: none;
}
QTabWidget::pane {
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    background: white;
    margin-top: 5px;
}
QTabBar::tab {
    background: #ecf0f1;
    color: #2c3e50;
    padding: 8px 16px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    border: 1px solid #bdc3c7;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #3498db;
    color: white;
    border-bottom: 2px solid #2980b9;
}
QStatusBar {
    background-color: #ecf0f1;
    color: #7f8c8d;
    border-top: 1px solid #bdc3c7;
}
"""

# --- CLASSE DE ACESSO AOS DADOS ---
class Database:
    def __init__(self, filename=DB_FILENAME):
        self.conn = sqlite3.connect(filename)
        self.create_tables()
        self.create_views()

    def create_tables(self):
        c = self.conn.cursor()
        c.executescript("""
        -- Imóveis rurais
        CREATE TABLE IF NOT EXISTS imovel_rural (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cod_imovel TEXT UNIQUE NOT NULL,
            pais TEXT NOT NULL DEFAULT 'BR',
            moeda TEXT NOT NULL DEFAULT 'BRL',
            cad_itr TEXT,
            caepf TEXT,
            insc_estadual TEXT,
            nome_imovel TEXT NOT NULL,
            endereco TEXT NOT NULL,
            num TEXT,
            compl TEXT,
            bairro TEXT NOT NULL,
            uf TEXT NOT NULL,
            cod_mun TEXT NOT NULL,
            cep TEXT NOT NULL,
            tipo_exploracao INTEGER NOT NULL,
            participacao REAL NOT NULL DEFAULT 100.0,
            area_total REAL,
            area_utilizada REAL,
            data_cadastro DATE DEFAULT CURRENT_DATE
        );
        -- Contas bancárias
        CREATE TABLE IF NOT EXISTS conta_bancaria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cod_conta TEXT UNIQUE NOT NULL,
            pais_cta TEXT NOT NULL DEFAULT 'BR',
            banco TEXT,
            nome_banco TEXT NOT NULL,
            agencia TEXT NOT NULL,
            num_conta TEXT NOT NULL,
            saldo_inicial REAL DEFAULT 0,
            data_abertura DATE DEFAULT CURRENT_DATE
        );
        -- Participantes
        CREATE TABLE IF NOT EXISTS participante (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cpf_cnpj TEXT UNIQUE NOT NULL,
            nome TEXT NOT NULL,
            tipo_contraparte INTEGER NOT NULL,
            data_cadastro DATE DEFAULT CURRENT_DATE
        );
        -- Culturas
        CREATE TABLE IF NOT EXISTS cultura (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            tipo TEXT NOT NULL,
            ciclo TEXT,
            unidade_medida TEXT
        );
        -- Áreas de produção
        CREATE TABLE IF NOT EXISTS area_producao (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imovel_id INTEGER NOT NULL,
            cultura_id INTEGER NOT NULL,
            area REAL NOT NULL,
            data_plantio DATE,
            data_colheita_estimada DATE,
            produtividade_estimada REAL,
            FOREIGN KEY(imovel_id) REFERENCES imovel_rural(id),
            FOREIGN KEY(cultura_id) REFERENCES cultura(id)
        );
        -- Estoques
        CREATE TABLE IF NOT EXISTS estoque (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto TEXT NOT NULL,
            quantidade REAL NOT NULL,
            unidade_medida TEXT NOT NULL,
            valor_unitario REAL,
            local_armazenamento TEXT,
            data_entrada DATE DEFAULT CURRENT_DATE,
            data_validade DATE,
            imovel_id INTEGER,
            FOREIGN KEY(imovel_id) REFERENCES imovel_rural(id)
        );
        -- Lançamentos contábeis
        CREATE TABLE IF NOT EXISTS lancamento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data DATE NOT NULL,
            cod_imovel INTEGER NOT NULL,
            cod_conta INTEGER NOT NULL,
            num_doc TEXT,
            tipo_doc INTEGER NOT NULL,
            historico TEXT NOT NULL,
            id_participante INTEGER,
            tipo_lanc INTEGER NOT NULL,
            valor_entrada REAL DEFAULT 0,
            valor_saida REAL DEFAULT 0,
            saldo_final REAL NOT NULL,
            natureza_saldo TEXT NOT NULL,
            categoria TEXT,
            area_afetada INTEGER,
            quantidade REAL,
            unidade_medida TEXT,
            FOREIGN KEY(cod_imovel) REFERENCES imovel_rural(id),
            FOREIGN KEY(cod_conta) REFERENCES conta_bancaria(id),
            FOREIGN KEY(id_participante) REFERENCES participante(id),
            FOREIGN KEY(area_afetada) REFERENCES area_producao(id)
        );
        """)
        self.conn.commit()

    def create_views(self):
        c = self.conn.cursor()
        c.executescript("""
        -- Saldo atual das contas
        CREATE VIEW IF NOT EXISTS saldo_contas AS
        SELECT 
            cb.id,
            cb.cod_conta,
            cb.nome_banco,
            l.saldo_final * (CASE l.natureza_saldo WHEN 'P' THEN 1 ELSE -1 END) AS saldo_atual
        FROM conta_bancaria cb
        LEFT JOIN (
            SELECT cod_conta, MAX(id) AS max_id
            FROM lancamento
            GROUP BY cod_conta
        ) last_l ON cb.id = last_l.cod_conta
        LEFT JOIN lancamento l ON last_l.max_id = l.id;
        -- Resumo por categoria
        CREATE VIEW IF NOT EXISTS resumo_categorias AS
        SELECT 
            categoria,
            SUM(valor_entrada) AS total_entradas,
            SUM(valor_saida) AS total_saidas,
            strftime('%Y', data) AS ano,
            strftime('%m', data) AS mes
        FROM lancamento
        GROUP BY categoria, ano, mes;
        """)
        self.conn.commit()

    def execute_query(self, sql, params=None):
        c = self.conn.cursor()
        c.execute(sql, params or [])
        self.conn.commit()
        return c

    def fetch_all(self, sql, params=None):
        return self.execute_query(sql, params).fetchall()

    def fetch_one(self, sql, params=None):
        return self.execute_query(sql, params).fetchone()

    def close(self):
        self.conn.close()


# --- DIALOG BASE PARA CADASTROS ---
class CadastroBaseDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(600, 500)
        self.db = Database()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self._add_header(title)
        self.form_layout = QFormLayout()
        self.layout.addLayout(self.form_layout)
        self._add_buttons()

    def _add_header(self, text):
        lbl = QLabel(text)
        lbl.setFont(QFont('', 16, QFont.Bold))
        lbl.setStyleSheet("color: #2c3e50; margin-bottom: 15px;")
        self.layout.addWidget(lbl)

    def _add_buttons(self):
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 20, 0, 0)
        btn_layout.addStretch()
        self.btn_salvar = QPushButton("Salvar")
        self.btn_salvar.setObjectName("success")
        self.btn_salvar.clicked.connect(self.salvar)
        btn_layout.addWidget(self.btn_salvar)
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.setObjectName("danger")
        btn_cancelar.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancelar)
        self.layout.addLayout(btn_layout)

    def salvar(self):
        raise NotImplementedError


# --- DIALOG CÓDIGO DE IMÓVEL ---
class CadastroImovelDialog(CadastroBaseDialog):
    def __init__(self, parent=None, imovel_id=None):
        super().__init__("Cadastro de Imóvel Rural", parent)
        self.imovel_id = imovel_id
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        # Identificação do Imóvel
        grp_id = QGroupBox("Identificação do Imóvel")
        grp_id.setContentsMargins(10, 10, 10, 10)
        form_id = QFormLayout(grp_id)
        self.cod_imovel = QLineEdit(); self.cod_imovel.setPlaceholderText("Código único do imóvel")
        form_id.addRow("Código do Imóvel:", self.cod_imovel)
        self.nome_imovel = QLineEdit(); form_id.addRow("Nome do Imóvel:", self.nome_imovel)
        self.cad_itr = QLineEdit(); form_id.addRow("CAD ITR:", self.cad_itr)
        self.caepf = QLineEdit(); form_id.addRow("CAEPF:", self.caepf)
        self.insc_estadual = QLineEdit(); form_id.addRow("Inscrição Estadual:", self.insc_estadual)
        self.form_layout.addRow(grp_id)

        # Localização
        grp_loc = QGroupBox("Localização")
        grp_loc.setContentsMargins(10, 10, 10, 10)
        form_loc = QFormLayout(grp_loc)
        self.endereco = QLineEdit(); form_loc.addRow("Endereço:", self.endereco)
        hl = QHBoxLayout(); hl.setContentsMargins(0, 0, 0, 0)
        self.num = QLineEdit(); self.num.setMaximumWidth(80); hl.addWidget(self.num)
        self.compl = QLineEdit(); self.compl.setPlaceholderText("Complemento"); hl.addWidget(self.compl)
        form_loc.addRow("Número/Complemento:", hl)
        self.bairro = QLineEdit(); form_loc.addRow("Bairro:", self.bairro)
        hl2 = QHBoxLayout(); hl2.setContentsMargins(0, 0, 0, 0)
        self.uf = QLineEdit(); self.uf.setMaximumWidth(50); hl2.addWidget(self.uf)
        self.cod_mun = QLineEdit(); self.cod_mun.setPlaceholderText("Cód. Município"); hl2.addWidget(self.cod_mun)
        self.cep = QLineEdit(); hl2.addWidget(self.cep)
        form_loc.addRow("UF / Cód. Mun. / CEP:", hl2)
        self.form_layout.addRow(grp_loc)

        # Exploração Agrícola
        grp_exp = QGroupBox("Exploração Agrícola")
        grp_exp.setContentsMargins(10, 10, 10, 10)
        form_exp = QFormLayout(grp_exp)
        self.tipo_exploracao = QComboBox()
        self.tipo_exploracao.addItems([
            "1 - Exploração individual", "2 - Condomínio", "3 - Imóvel arrendado",
            "4 - Parceria", "5 - Comodato", "6 - Outros"
        ])
        form_exp.addRow("Tipo de Exploração:", self.tipo_exploracao)
        self.participacao = QLineEdit("100.00"); form_exp.addRow("Participação (%):", self.participacao)
        hl3 = QHBoxLayout(); hl3.setContentsMargins(0, 0, 0, 0)
        self.area_total = QLineEdit(); self.area_total.setPlaceholderText("Total (ha)"); hl3.addWidget(self.area_total)
        self.area_utilizada = QLineEdit(); self.area_utilizada.setPlaceholderText("Utilizada (ha)"); hl3.addWidget(self.area_utilizada)
        form_exp.addRow("Área (ha):", hl3)
        self.form_layout.addRow(grp_exp)

    def load_data(self):
        # intervalo do filtro
        d1 = self.dt_dash_ini.date().toString("yyyy-MM-dd")
        d2 = self.dt_dash_fim.date().toString("yyyy-MM-dd")

        # soma de entradas e saídas no intervalo
        rec = self.db.fetch_one(
            "SELECT SUM(valor_entrada) FROM lancamento WHERE data BETWEEN ? AND ?", (d1, d2)
        )[0] or 0.0
        desp = self.db.fetch_one(
            "SELECT SUM(valor_saida)   FROM lancamento WHERE data BETWEEN ? AND ?", (d1, d2)
        )[0] or 0.0

        # SALDO TOTAL = RECEITAS − DESPESAS
        saldo_liquido = rec - desp

        # atualiza os cartões
        self.saldo_card.findChild(QLabel, "value").setText(f"R$ {saldo_liquido:,.2f}")
        self.receita_card.findChild(QLabel, "value").setText(f"R$ {rec:,.2f}")
        self.despesa_card.findChild(QLabel, "value").setText(f"R$ {desp:,.2f}")

        # atualizar o gráfico de pizza com percentuais
        self.series.clear()
        slice_rec = self.series.append("Receitas", rec)
        slice_desp = self.series.append("Despesas", desp)
        for slice in self.series.slices():
            pct = slice.percentage() * 100
            slice.setLabelVisible(True)
            slice.setLabel(f"{slice.label()} ({pct:.1f}%)")

    def salvar(self):
        campos = [
            self.cod_imovel.text(), self.nome_imovel.text(),
            self.endereco.text(), self.bairro.text(),
            self.uf.text(), self.cod_mun.text(), self.cep.text()
        ]
        if not all(campos):
            QMessageBox.warning(self, "Campos Obrigatórios", "Preencha todos os campos obrigatórios!")
            return
        try:
            data = (
                self.cod_imovel.text(), self.nome_imovel.text(), self.cad_itr.text(),
                self.caepf.text(), self.insc_estadual.text(),
                self.endereco.text(), self.num.text(), self.compl.text(),
                self.bairro.text(), self.uf.text(), self.cod_mun.text(),
                self.cep.text(), self.tipo_exploracao.currentIndex()+1,
                float(self.participacao.text()),
                float(self.area_total.text()) if self.area_total.text() else None,
                float(self.area_utilizada.text()) if self.area_utilizada.text() else None
            )
            if self.imovel_id:
                self.db.execute_query("""
                    UPDATE imovel_rural SET
                        cod_imovel=?, nome_imovel=?, cad_itr=?, caepf=?, insc_estadual=?,
                        endereco=?, num=?, compl=?, bairro=?, uf=?, cod_mun=?, cep=?,
                        tipo_exploracao=?, participacao=?, area_total=?, area_utilizada=?
                    WHERE id=?
                """, data + (self.imovel_id,))
                msg = "Imóvel atualizado com sucesso!"
            else:
                self.db.execute_query("""
                    INSERT INTO imovel_rural (
                        cod_imovel, nome_imovel, cad_itr, caepf, insc_estadual,
                        endereco, num, compl, bairro, uf, cod_mun, cep,
                        tipo_exploracao, participacao, area_total, area_utilizada
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, data)
                msg = "Imóvel cadastrado com sucesso!"
            QMessageBox.information(self, "Sucesso", msg)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar imóvel: {e}")


# --- DIALOG CADASTRO CONTA BANCÁRIA ---
class CadastroContaDialog(CadastroBaseDialog):
    def __init__(self, parent=None, conta_id=None):
        super().__init__("Cadastro de Conta Bancária", parent)
        self.conta_id = conta_id
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        grp1 = QGroupBox("Identificação da Conta")
        grp1.setContentsMargins(10, 10, 10, 10)
        f1 = QFormLayout(grp1)
        self.cod_conta = QLineEdit(); self.cod_conta.setPlaceholderText("Código único da conta")
        f1.addRow("Código da Conta:", self.cod_conta)
        self.nome_banco = QLineEdit(); f1.addRow("Nome do Banco:", self.nome_banco)
        self.banco = QLineEdit(); f1.addRow("Código do Banco:", self.banco)
        self.form_layout.addRow(grp1)
        grp2 = QGroupBox("Dados Bancários")
        grp2.setContentsMargins(10, 10, 10, 10)
        f2 = QFormLayout(grp2)
        self.agencia = QLineEdit(); f2.addRow("Agência:", self.agencia)
        self.num_conta = QLineEdit(); f2.addRow("Número da Conta:", self.num_conta)
        self.saldo_inicial = QLineEdit("0.00"); f2.addRow("Saldo Inicial:", self.saldo_inicial)
        self.form_layout.addRow(grp2)

    def _load_data(self):
        if not self.conta_id: return
        row = self.db.fetch_one("SELECT * FROM conta_bancaria WHERE id=?", (self.conta_id,))
        if not row: return
        (_, cod, pais, banco, nome, agencia, num, saldo, _) = row
        self.cod_conta.setText(cod)
        self.banco.setText(banco or "")
        self.nome_banco.setText(nome)
        self.agencia.setText(agencia)
        self.num_conta.setText(num)
        self.saldo_inicial.setText(str(saldo))

    def salvar(self):
        if not all([self.cod_conta.text(), self.nome_banco.text(),
                    self.agencia.text(), self.num_conta.text()]):
            QMessageBox.warning(self, "Campos Obrigatórios", "Preencha todos os campos obrigatórios!")
            return
        try:
            saldo = float(self.saldo_inicial.text().replace(',', '.'))
            data = (
                self.cod_conta.text(), "BR", self.banco.text() or "",
                self.nome_banco.text(), self.agencia.text(),
                self.num_conta.text(), saldo
            )
            if self.conta_id:
                self.db.execute_query("""
                    UPDATE conta_bancaria SET
                        cod_conta=?, pais_cta=?, banco=?, nome_banco=?,
                        agencia=?, num_conta=?, saldo_inicial=?
                    WHERE id=?
                """, data + (self.conta_id,))
                msg = "Conta atualizada com sucesso!"
            else:
                self.db.execute_query("""
                    INSERT INTO conta_bancaria (
                        cod_conta, pais_cta, banco, nome_banco,
                        agencia, num_conta, saldo_inicial
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, data)
                msg = "Conta cadastrada com sucesso!"
            QMessageBox.information(self, "Sucesso", msg)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar conta: {e}")


# --- DIALOG CADASTRO PARTICIPANTE ---
class CadastroParticipanteDialog(QDialog):
    def __init__(self, parent=None, participante_id=None):
        super().__init__(parent)
        self.participante_id = participante_id
        self.setWindowTitle("Cadastro de Participante")
        self.setMinimumSize(400, 250)
        self.db = Database()
        self.layout = QVBoxLayout(self)
        self._add_header()
        self.form_layout = QFormLayout()
        self.layout.addLayout(self.form_layout)
        self._build_ui()
        self._add_buttons()
        self._load_data()

    def _add_header(self):
        lbl = QLabel("Cadastro de Participante")
        lbl.setFont(QFont('', 16, QFont.Bold))
        lbl.setStyleSheet("color: #2c3e50; margin-bottom: 15px;")
        self.layout.addWidget(lbl)

    def _build_ui(self):
        grp = QGroupBox("Dados do Participante")
        grp.setContentsMargins(10, 10, 10, 10)
        form = QFormLayout(grp)
        self.cpf_cnpj = QLineEdit()
        self.cpf_cnpj.setPlaceholderText("Digite CPF ou CNPJ")
        self.cpf_cnpj.textChanged.connect(self._ajustar_mask_cpf_cnpj)
        form.addRow("CPF/CNPJ:", self.cpf_cnpj)
        self.nome = QLineEdit()
        form.addRow("Nome:", self.nome)
        self.tipo = QComboBox()
        self.tipo.addItems(["Pessoa Física", "Pessoa Jurídica", "Órgão Público", "Outros"])
        form.addRow("Tipo:", self.tipo)
        self.form_layout.addRow(grp)

    def _ajustar_mask_cpf_cnpj(self, texto: str):
        digits = ''.join(filter(str.isdigit, texto))
        cursor = self.cpf_cnpj.cursorPosition()
        if len(digits) <= 11:
            self.cpf_cnpj.setInputMask("000.000.000-00;_")
        else:
            self.cpf_cnpj.setInputMask("00.000.000/0000-00;_")
        self.cpf_cnpj.setCursorPosition(cursor)

    def _add_buttons(self):
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_salvar = QPushButton("Salvar")
        self.btn_salvar.setObjectName("success")
        self.btn_salvar.clicked.connect(self.salvar)
        btn_layout.addWidget(self.btn_salvar)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setObjectName("danger")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        self.layout.addLayout(btn_layout)

    def _load_data(self):
        if not self.participante_id:
            return
        row = self.db.fetch_one(
            "SELECT cpf_cnpj, nome, tipo_contraparte FROM participante WHERE id = ?",
            (self.participante_id,)
        )
        if row:
            self.cpf_cnpj.setText(row[0])
            self.nome.setText(row[1])
            self.tipo.setCurrentIndex(row[2]-1)

    def salvar(self):
        if not self.cpf_cnpj.hasAcceptableInput() or not self.nome.text().strip():
            QMessageBox.warning(self, "Campos Inválidos", "Preencha corretamente CPF/CNPJ e Nome.")
            return
        data = (
            self.cpf_cnpj.text(),
            self.nome.text().strip(),
            self.tipo.currentIndex()+1
        )
        try:
            if self.participante_id:
                self.db.execute_query(
                    "UPDATE participante SET cpf_cnpj=?, nome=?, tipo_contraparte=? WHERE id=?",
                    data + (self.participante_id,)
                )
            else:
                self.db.execute_query(
                    "INSERT INTO participante (cpf_cnpj, nome, tipo_contraparte) VALUES (?,?,?)",
                    data
                )
            QMessageBox.information(self, "Sucesso", "Participante salvo com sucesso!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar participante: {e}")


# --- DIALOG PARA LANÇAMENTOS CONTÁBEIS ---
class LancamentoDialog(QDialog):
    def __init__(self, parent=None, lanc_id=None):
        super().__init__(parent)
        self.lanc_id = lanc_id
        self.setWindowTitle("Lançamento Contábil")
        self.setMinimumSize(700, 500)
        self.db = Database()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        form = QFormLayout()
        # Data
        self.data = QDateEdit(QDate.currentDate())
        self.data.setCalendarPopup(True)
        form.addRow("Data:", self.data)
        # Imóvel
        self.imovel = QComboBox()
        self.imovel.addItem("Selecione...", None)
        for id_, nome in self.db.fetch_all("SELECT id, nome_imovel FROM imovel_rural"):
            self.imovel.addItem(nome, id_)
        form.addRow("Imóvel Rural:", self.imovel)
        # Conta
        self.conta = QComboBox()
        self.conta.addItem("Selecione...", None)
        for id_, nome in self.db.fetch_all("SELECT id, nome_banco FROM conta_bancaria"):
            self.conta.addItem(nome, id_)
        form.addRow("Conta Bancária:", self.conta)
        # Participante
        self.participante = QComboBox()
        self.participante.addItem("Selecione...", None)
        for id_, nome in self.db.fetch_all("SELECT id, nome FROM participante"):
            self.participante.addItem(nome, id_)
        form.addRow("Participante:", self.participante)
        # Documento
        hl = QHBoxLayout(); hl.setContentsMargins(0,0,0,0)
        self.num_doc = QLineEdit(); hl.addWidget(QLabel("Número:")); hl.addWidget(self.num_doc)
        self.tipo_doc = QComboBox()
        self.tipo_doc.addItems(["Nota Fiscal", "Recibo", "Boleto", "Outros"])
        hl.addWidget(QLabel("Tipo:")); hl.addWidget(self.tipo_doc)
        form.addRow("Documento:", hl)
        # Histórico
        self.historico = QLineEdit(); form.addRow("Histórico:", self.historico)
        # Tipo lançamento
        self.tipo_lanc = QComboBox()
        self.tipo_lanc.addItems(["1 - Receita", "2 - Despesa", "3 - Adiantamento"])
        form.addRow("Tipo de Lançamento:", self.tipo_lanc)
        # Valores
        hl2 = QHBoxLayout(); hl2.setContentsMargins(0,0,0,0)
        self.valor_entrada = QLineEdit("0.00"); hl2.addWidget(QLabel("Entrada:")); hl2.addWidget(self.valor_entrada)
        self.valor_saida = QLineEdit("0.00"); hl2.addWidget(QLabel("Saída:")); hl2.addWidget(self.valor_saida)
        form.addRow("Valor:", hl2)
        # Categoria
        self.categoria = QComboBox()
        self.categoria.addItems([
            "Sementes","Adubos","Defensivos","Combustível",
            "Manutenção","Mão de Obra","Venda de Produtos",
            "Serviços","Outros"
        ])
        form.addRow("Categoria:", self.categoria)

        self.layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.salvar)
        btns.rejected.connect(self.reject)
        self.layout.addWidget(btns)

    def _load_data(self):
        if not self.lanc_id:
            return
        row = self.db.fetch_one(
            "SELECT data, cod_imovel, cod_conta, num_doc, tipo_doc, historico, "
            "id_participante, tipo_lanc, valor_entrada, valor_saida, natureza_saldo, categoria "
            "FROM lancamento WHERE id=?", (self.lanc_id,)
        )
        if row:
            self.data.setDate(QDate.fromString(row[0], "yyyy-MM-dd"))
            self.imovel.setCurrentIndex(self.imovel.findData(row[1]))
            self.conta.setCurrentIndex(self.conta.findData(row[2]))
            self.num_doc.setText(row[3] or "")
            self.tipo_doc.setCurrentIndex(row[4]-1)
            self.historico.setText(row[5])
            self.participante.setCurrentIndex(self.participante.findData(row[6]))
            self.tipo_lanc.setCurrentIndex(row[7]-1)
            self.valor_entrada.setText(f"{row[8]:.2f}")
            self.valor_saida.setText(f"{row[9]:.2f}")
            self.categoria.setCurrentText(row[11])

    def salvar(self):
        if not (self.imovel.currentData() and self.conta.currentData() and self.historico.text()):
            QMessageBox.warning(self, "Campos Obrigatórios", "Preencha todos os campos obrigatórios!")
            return
        try:
            ent = float(self.valor_entrada.text().replace(',', '.'))
            sai = float(self.valor_saida.text().replace(',', '.'))
            if self.lanc_id:
                self.db.execute_query("""
                    UPDATE lancamento SET
                        data=?, cod_imovel=?, cod_conta=?, num_doc=?, tipo_doc=?, historico=?,
                        id_participante=?, tipo_lanc=?, valor_entrada=?, valor_saida=?, natureza_saldo=?, categoria=?
                    WHERE id=?
                """, (
                    self.data.date().toString("yyyy-MM-dd"),
                    self.imovel.currentData(), self.conta.currentData(),
                    self.num_doc.text() or None, self.tipo_doc.currentIndex()+1, self.historico.text(),
                    self.participante.currentData(), self.tipo_lanc.currentIndex()+1,
                    ent, sai,
                    'P' if ent - sai >= 0 else 'N',
                    self.categoria.currentText(),
                    self.lanc_id
                ))
            else:
                prev = self.db.fetch_one(
                    "SELECT saldo_final FROM lancamento WHERE cod_conta=? ORDER BY id DESC LIMIT 1",
                    (self.conta.currentData(),)
                )
                saldo_ant = prev[0] if prev else 0.0
                saldo_f = saldo_ant + ent - sai
                nat = 'P' if saldo_f >= 0 else 'N'
                self.db.execute_query("""
                    INSERT INTO lancamento (
                        data, cod_imovel, cod_conta, num_doc, tipo_doc, historico,
                        id_participante, tipo_lanc, valor_entrada, valor_saida,
                        saldo_final, natureza_saldo, categoria
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    self.data.date().toString("yyyy-MM-dd"),
                    self.imovel.currentData(), self.conta.currentData(),
                    self.num_doc.text() or None, self.tipo_doc.currentIndex()+1, self.historico.text(),
                    self.participante.currentData(), self.tipo_lanc.currentIndex()+1,
                    ent, sai, abs(saldo_f), nat, self.categoria.currentText()
                ))
            QMessageBox.information(self, "Sucesso", "Lançamento salvo com sucesso!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao salvar lançamento: {e}")


# --- DIALOG DE RELATÓRIO POR PERÍODO ---
class RelatorioPeriodoDialog(QDialog):
    def __init__(self, tipo, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tipo)
        self.setMinimumSize(300, 150)
        layout = QFormLayout(self)
        self.dt_ini = QDateEdit(QDate.currentDate().addMonths(-1))
        self.dt_ini.setCalendarPopup(True)
        layout.addRow("Data inicial:", self.dt_ini)
        self.dt_fim = QDateEdit(QDate.currentDate())
        self.dt_fim.setCalendarPopup(True)
        layout.addRow("Data final:", self.dt_fim)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    @property
    def periodo(self):
        return (
            self.dt_ini.date().toString("yyyy-MM-dd"),
            self.dt_fim.date().toString("yyyy-MM-dd")
        )


# --- WIDGET DASHBOARD (Painel) COM FILTRO INICIAL/FINAL E %
class DashboardWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = Database()
        self.settings = QSettings("PrimeOnHub", "AgroApp")
        self.layout = QVBoxLayout(self)
        self._build_filter_ui()
        self._build_cards_ui()
        self._build_piechart_ui()
        self.load_data()

    def _build_filter_ui(self):
        hl = QHBoxLayout()
        hl.addWidget(QLabel("De:"))
        ini = self.settings.value("dashFilterIni", QDate.currentDate().addMonths(-1), type=QDate)
        self.dt_dash_ini = QDateEdit(ini); self.dt_dash_ini.setCalendarPopup(True)
        hl.addWidget(self.dt_dash_ini)
        hl.addWidget(QLabel("Até:"))
        fim = self.settings.value("dashFilterFim", QDate.currentDate(), type=QDate)
        self.dt_dash_fim = QDateEdit(fim); self.dt_dash_fim.setCalendarPopup(True)
        hl.addWidget(self.dt_dash_fim)
        btn = QPushButton("Aplicar filtro"); btn.clicked.connect(self.on_dash_filter_changed)
        hl.addWidget(btn)
        hl.addStretch()
        self.layout.addLayout(hl)

    def _build_cards_ui(self):
        self.cards_layout = QHBoxLayout()
        self.cards_layout.setSpacing(20)
        self.saldo_card = self._card("Saldo Total", "R$ 0,00", "#2ecc71")
        self.receita_card = self._card("Receitas", "R$ 0,00", "#3498db")
        self.despesa_card = self._card("Despesas", "R$ 0,00", "#e74c3c")
        for c in [self.saldo_card, self.receita_card, self.despesa_card]:
            self.cards_layout.addWidget(c, 1)
        self.layout.addLayout(self.cards_layout)

    def _build_piechart_ui(self):
        self.pie_group = QGroupBox("Receitas x Despesas")
        gl = QVBoxLayout(self.pie_group)
        self.series = QPieSeries()
        chart = QChart(); chart.addSeries(self.series)
        chart.setAnimationOptions(QChart.SeriesAnimations)
        self.chart_view = QChartView(chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        gl.addWidget(self.chart_view)
        self.layout.addWidget(self.pie_group)

    def _card(self, title, value, color):
        frm = QFrame()
        frm.setStyleSheet(f"""
            QFrame {{ background-color:white; border-radius:8px; border-left:5px solid {color}; padding:15px; }}
            QLabel#title {{ color:#7f8c8d; font-size:14px; }}
            QLabel#value {{ color:#2c3e50; font-size:24px; font-weight:bold; }}
        """)
        fl = QVBoxLayout(frm)
        t = QLabel(title); t.setObjectName("title")
        v = QLabel(value); v.setObjectName("value")
        fl.addWidget(t); fl.addWidget(v)
        return frm

    def on_dash_filter_changed(self):
        self.settings.setValue("dashFilterIni", self.dt_dash_ini.date())
        self.settings.setValue("dashFilterFim", self.dt_dash_fim.date())
        self.load_data()

    def load_data(self):
        d1 = self.dt_dash_ini.date().toString("yyyy-MM-dd")
        d2 = self.dt_dash_fim.date().toString("yyyy-MM-dd")
        # Saldo total
        saldo = self.db.fetch_one("SELECT SUM(saldo_atual) FROM saldo_contas")[0] or 0
        self.saldo_card.findChild(QLabel, "value").setText(f"R$ {saldo:,.2f}")
        # Receitas e Despesas no intervalo
        rec = self.db.fetch_one(
            "SELECT SUM(valor_entrada) FROM lancamento WHERE data BETWEEN ? AND ?", (d1, d2)
        )[0] or 0
        desp = self.db.fetch_one(
            "SELECT SUM(valor_saida)   FROM lancamento WHERE data BETWEEN ? AND ?", (d1, d2)
        )[0] or 0
        self.receita_card.findChild(QLabel, "value").setText(f"R$ {rec:,.2f}")
        self.despesa_card.findChild(QLabel, "value").setText(f"R$ {desp:,.2f}")
        # Gráfico de pizza com %
        self.series.clear()
        s1 = self.series.append("Receitas", rec)
        s2 = self.series.append("Despesas", desp)
        for slice in self.series.slices():
            pct = slice.percentage() * 100
            slice.setLabelVisible(True)
            slice.setLabel(f"{slice.label()} ({pct:.1f}%)")


# --- WIDGET GERENCIAMENTO IMÓVEIS ---
class GerenciamentoImoveisWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = Database()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self._build_ui()
        self.carregar_imoveis()

    def _build_ui(self):
        tl = QHBoxLayout(); tl.setContentsMargins(0, 0, 10, 10)
        self.btn_novo = QPushButton("Novo Imóvel"); self.btn_novo.clicked.connect(self.novo_imovel)
        self.btn_novo.setIcon(QIcon.fromTheme("document-new")); tl.addWidget(self.btn_novo)
        self.btn_editar = QPushButton("Editar"); self.btn_editar.setEnabled(False)
        self.btn_editar.clicked.connect(self.editar_imovel)
        self.btn_editar.setIcon(QIcon.fromTheme("document-edit")); tl.addWidget(self.btn_editar)
        self.btn_excluir = QPushButton("Excluir"); self.btn_excluir.setEnabled(False)
        self.btn_excluir.clicked.connect(self.excluir_imovel)
        self.btn_excluir.setIcon(QIcon.fromTheme("edit-delete")); tl.addWidget(self.btn_excluir)
        tl.addStretch()
        self.pesquisa = QLineEdit(); self.pesquisa.setPlaceholderText("Pesquisar imóveis...")
        self.pesquisa.textChanged.connect(self.carregar_imoveis); tl.addWidget(self.pesquisa)
        self.layout.addLayout(tl)

        self.tabela = QTableWidget(0, 6)
        self.tabela.setHorizontalHeaderLabels(["Código","Nome","UF","Área Total","Área Utilizada","Participação"])
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.cellClicked.connect(self._select_row)
        self.layout.addWidget(self.tabela)

    def carregar_imoveis(self):
        termo = f"%{self.pesquisa.text()}%"
        rows = self.db.fetch_all("""
            SELECT id,cod_imovel,nome_imovel,uf,area_total,area_utilizada,participacao
            FROM imovel_rural
            WHERE cod_imovel LIKE ? OR nome_imovel LIKE ?
            ORDER BY nome_imovel
        """, (termo, termo))
        self.tabela.setRowCount(len(rows))
        for r,(id_,cod,nome,uf,at,au,part) in enumerate(rows):
            for c,val in enumerate([
                cod, nome, uf,
                f"{at or 0:.2f} ha",
                f"{au or 0:.2f} ha",
                f"{part:.2f}%"
            ]):
                item = QTableWidgetItem(val)
                self.tabela.setItem(r, c, item)
            self.tabela.item(r, 0).setData(Qt.UserRole, id_)

    def _select_row(self, row, _):
        self.selected_row = row
        self.btn_editar.setEnabled(True)
        self.btn_excluir.setEnabled(True)

    def novo_imovel(self):
        dlg = CadastroImovelDialog(self)
        if dlg.exec():
            self.carregar_imoveis()

    def editar_imovel(self):
        id_ = self.tabela.item(self.selected_row, 0).data(Qt.UserRole)
        dlg = CadastroImovelDialog(self, id_)
        if dlg.exec():
            self.carregar_imoveis()

    def excluir_imovel(self):
        id_ = self.tabela.item(self.selected_row, 0).data(Qt.UserRole)
        nome = self.tabela.item(self.selected_row, 1).text()
        ans = QMessageBox.question(self, "Confirmar Exclusão",
                                   f"Excluir imóvel '{nome}'?",
                                   QMessageBox.Yes | QMessageBox.No)
        if ans == QMessageBox.Yes:
            try:
                self.db.execute_query("DELETE FROM imovel_rural WHERE id=?", (id_,))
                QMessageBox.information(self, "Sucesso", "Imóvel excluído!")
                self.carregar_imoveis()
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao excluir: {e}")


# --- WIDGET GERENCIAMENTO CONTAS ---
class GerenciamentoContasWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = Database()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self._build_ui()
        self.carregar_contas()

    def _build_ui(self):
        tl = QHBoxLayout(); tl.setContentsMargins(0,0,10,10)
        self.btn_novo = QPushButton("Nova Conta"); self.btn_novo.clicked.connect(self.nova_conta)
        self.btn_novo.setIcon(QIcon.fromTheme("document-new")); tl.addWidget(self.btn_novo)
        self.btn_editar = QPushButton("Editar"); self.btn_editar.setEnabled(False)
        self.btn_editar.clicked.connect(self.editar_conta)
        self.btn_editar.setIcon(QIcon.fromTheme("document-edit")); tl.addWidget(self.btn_editar)
        self.btn_excluir = QPushButton("Excluir"); self.btn_excluir.setEnabled(False)
        self.btn_excluir.clicked.connect(self.excluir_conta)
        self.btn_excluir.setIcon(QIcon.fromTheme("edit-delete")); tl.addWidget(self.btn_excluir)
        tl.addStretch()
        self.layout.addLayout(tl)

        self.tabela = QTableWidget(0,5)
        self.tabela.setHorizontalHeaderLabels(["Código","Banco","Agência","Conta","Saldo Inicial"])
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.cellClicked.connect(self._select_row)
        self.layout.addWidget(self.tabela)

    def carregar_contas(self):
        rows = self.db.fetch_all("SELECT id,cod_conta,nome_banco,agencia,num_conta,saldo_inicial FROM conta_bancaria ORDER BY nome_banco")
        self.tabela.setRowCount(len(rows))
        for r,(id_,cod,banco,ag,cont,saldo) in enumerate(rows):
            for c,val in enumerate([cod,banco,ag,cont,f"R$ {saldo:,.2f}"]):
                self.tabela.setItem(r,c, QTableWidgetItem(val))
            self.tabela.item(r,0).setData(Qt.UserRole, id_)

    def _select_row(self, row, _):
        self.selected_row = row
        self.btn_editar.setEnabled(True)
        self.btn_excluir.setEnabled(True)

    def nova_conta(self):
        dlg = CadastroContaDialog(self)
        if dlg.exec():
            self.carregar_contas()

    def editar_conta(self):
        id_ = self.tabela.item(self.selected_row,0).data(Qt.UserRole)
        dlg = CadastroContaDialog(self, id_)
        if dlg.exec():
            self.carregar_contas()

    def excluir_conta(self):
        id_ = self.tabela.item(self.selected_row,0).data(Qt.UserRole)
        cod = self.tabela.item(self.selected_row,1).text()
        ans = QMessageBox.question(self,"Confirmar Exclusão",f"Excluir conta '{cod}'?",QMessageBox.Yes|QMessageBox.No)
        if ans==QMessageBox.Yes:
            try:
                self.db.execute_query("DELETE FROM conta_bancaria WHERE id=?", (id_,))
                QMessageBox.information(self,"Sucesso","Conta excluída!")
                self.carregar_contas()
            except Exception as e:
                QMessageBox.critical(self,"Erro",f"Erro ao excluir: {e}")


# --- WIDGET GERENCIAMENTO PARTICIPANTES ---
class GerenciamentoParticipantesWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = Database()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10,10,10,10)
        self._build_ui()
        self.carregar_participantes()

    def _build_ui(self):
        tl = QHBoxLayout(); tl.setContentsMargins(0,0,10,10)
        self.btn_novo = QPushButton("Novo Participante"); self.btn_novo.clicked.connect(self.novo_participante)
        self.btn_novo.setIcon(QIcon.fromTheme("document-new")); tl.addWidget(self.btn_novo)
        self.btn_editar = QPushButton("Editar"); self.btn_editar.setEnabled(False)
        self.btn_editar.clicked.connect(self.editar_participante)
        self.btn_editar.setIcon(QIcon.fromTheme("document-edit")); tl.addWidget(self.btn_editar)
        self.btn_excluir = QPushButton("Excluir"); self.btn_excluir.setEnabled(False)
        self.btn_excluir.clicked.connect(self.excluir_participante)
        self.btn_excluir.setIcon(QIcon.fromTheme("edit-delete")); tl.addWidget(self.btn_excluir)
        tl.addStretch()
        self.layout.addLayout(tl)

        self.tabela = QTableWidget(0,4)
        self.tabela.setHorizontalHeaderLabels(["CPF/CNPJ","Nome","Tipo","Cadastro"])
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.cellClicked.connect(self._select_row)
        self.layout.addWidget(self.tabela)

    def carregar_participantes(self):
        rows = self.db.fetch_all("SELECT id,cpf_cnpj,nome,tipo_contraparte,data_cadastro FROM participante ORDER BY data_cadastro DESC")
        self.tabela.setRowCount(len(rows))
        tipos = {1:"PF",2:"PJ",3:"Órgão Público",4:"Outros"}
        for r,(id_,cpf,nome,tipo,data) in enumerate(rows):
            for c,val in enumerate([cpf,nome,tipos.get(tipo,str(tipo)),data]):
                self.tabela.setItem(r,c, QTableWidgetItem(val))
            self.tabela.item(r,0).setData(Qt.UserRole,id_)

    def _select_row(self,row,_):
        self.selected_row = row
        self.btn_editar.setEnabled(True)
        self.btn_excluir.setEnabled(True)

    def novo_participante(self):
        dlg = CadastroParticipanteDialog(self)
        if dlg.exec():
            self.carregar_participantes()

    def editar_participante(self):
        id_ = self.tabela.item(self.selected_row,0).data(Qt.UserRole)
        dlg = CadastroParticipanteDialog(self,id_)
        if dlg.exec():
            self.carregar_participantes()

    def excluir_participante(self):
        id_ = self.tabela.item(self.selected_row,0).data(Qt.UserRole)
        nome = self.tabela.item(self.selected_row,1).text()
        ans = QMessageBox.question(self,"Confirmar Exclusão",f"Excluir participante '{nome}'?",QMessageBox.Yes|QMessageBox.No)
        if ans==QMessageBox.Yes:
            try:
                self.db.execute_query("DELETE FROM participante WHERE id=?", (id_,))
                QMessageBox.information(self,"Sucesso","Participante excluído!")
                self.carregar_participantes()
            except Exception as e:
                QMessageBox.critical(self,"Erro",f"Erro ao excluir: {e}")


# --- WIDGET CADASTROS COM ABAS ---
class CadastrosWidget(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabPosition(QTabWidget.West)
        self.addTab(GerenciamentoImoveisWidget(), "Imóveis")
        self.addTab(GerenciamentoContasWidget(), "Contas")
        self.addTab(GerenciamentoParticipantesWidget(), "Participantes")
        self.addTab(QWidget(), "Culturas")
        self.addTab(QWidget(), "Áreas")
        self.addTab(QWidget(), "Estoque")
        icons = ["home","credit-card","user-group","tree","map","box"]
        for i,ic in enumerate(icons):
            self.setTabIcon(i, QIcon.fromTheme(ic))


# --- JANELA PRINCIPAL ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sistema AgroContábil - LCDPR")
        self.setGeometry(100,100,1200,800)
        self.setStyleSheet(STYLE_SHEET)
        self.db = Database()
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowIcon(QIcon(APP_ICON))
        self._create_menu()
        self._create_toolbar()
        self.tabs = QTabWidget()
        self.tabs.setContentsMargins(10,10,10,10)
        self.setCentralWidget(self.tabs)

        # Painel
        self.dashboard = DashboardWidget()
        self.tabs.addTab(self.dashboard, "Painel")

        # Lançamentos
        w_l = QWidget(); l_l = QVBoxLayout(w_l); l_l.setContentsMargins(10,10,10,10)
        self.lanc_filter_layout = QHBoxLayout()
        self.lanc_filter_layout.addWidget(QLabel("De:"))
        self.dt_ini = QDateEdit(QDate.currentDate().addMonths(-1)); self.dt_ini.setCalendarPopup(True)
        self.lanc_filter_layout.addWidget(self.dt_ini)
        self.lanc_filter_layout.addWidget(QLabel("Até:"))
        self.dt_fim = QDateEdit(QDate.currentDate()); self.dt_fim.setCalendarPopup(True)
        self.lanc_filter_layout.addWidget(self.dt_fim)
        btn_filtrar = QPushButton("Filtrar"); btn_filtrar.clicked.connect(self.carregar_lancamentos)
        self.lanc_filter_layout.addWidget(btn_filtrar)
        self.btn_edit_lanc = QPushButton("Editar Lançamento"); self.btn_edit_lanc.setEnabled(False)
        self.btn_edit_lanc.clicked.connect(self.editar_lancamento)
        self.lanc_filter_layout.addWidget(self.btn_edit_lanc)
        self.btn_del_lanc = QPushButton("Excluir Lançamento"); self.btn_del_lanc.setEnabled(False)
        self.btn_del_lanc.clicked.connect(self.excluir_lancamento)
        self.lanc_filter_layout.addWidget(self.btn_del_lanc)
        l_l.addLayout(self.lanc_filter_layout)

        self.tab_lanc = QTableWidget(0,8)
        self.tab_lanc.setHorizontalHeaderLabels(["ID","Data","Imóvel","Histórico","Tipo","Entrada","Saída","Saldo"])
        self.tab_lanc.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tab_lanc.setSelectionBehavior(QTableWidget.SelectRows)
        self.tab_lanc.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tab_lanc.cellClicked.connect(lambda r,_: (
            self.btn_edit_lanc.setEnabled(True),
            self.btn_del_lanc.setEnabled(True)
        ))
        l_l.addWidget(self.tab_lanc)
        self.tabs.addTab(w_l, "Lançamentos")

        # Cadastros
        self.cadw = CadastrosWidget()
        self.tabs.addTab(self.cadw, "Cadastros")

        # Planejamento
        w_p = QWidget(); l_p = QVBoxLayout(w_p); l_p.setContentsMargins(10,10,10,10)
        self.tab_plan = QTableWidget(0,5)
        self.tab_plan.setHorizontalHeaderLabels(["Cultura","Área","Plantio","Colheita Est.","Prod. Est."])
        self.tab_plan.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        l_p.addWidget(self.tab_plan)
        self.tabs.addTab(w_p, "Planejamento")

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Sistema iniciado com sucesso!")

        self.carregar_lancamentos()
        self.carregar_planejamento()

    def _create_menu(self):
        mb = self.menuBar()
        m1 = mb.addMenu("&Arquivo")
        a1 = QAction("Novo Lançamento", self); a1.triggered.connect(self.novo_lancamento)
        m1.addAction(a1)
        a2 = QAction("Exportar Dados", self); a2.triggered.connect(self.exportar_dados)
        m1.addAction(a2)
        m1.addSeparator()
        a3 = QAction("Sair", self); a3.triggered.connect(self.close)
        m1.addAction(a3)

        m2 = mb.addMenu("&Cadastros")
        for txt,fn in [
            ("Imóvel Rural", lambda: self.tabs.setCurrentIndex(1)),
            ("Conta Bancária", lambda: self.tabs.setCurrentIndex(2)),
            ("Participante", lambda: self.tabs.setCurrentIndex(3)),
            ("Cultura", lambda: QMessageBox.information(self,"Cultura","Em desenvolvimento"))
        ]:
            act = QAction(txt, self); act.triggered.connect(fn); m2.addAction(act)

        m3 = mb.addMenu("&Relatórios")
        bal = QAction("Balancete", self); bal.triggered.connect(self.abrir_balancete)
        m3.addAction(bal)
        raz = QAction("Razão", self); raz.triggered.connect(self.abrir_razao)
        m3.addAction(raz)

        m4 = mb.addMenu("&Ajuda")
        m4.addAction(QAction("Manual do Usuário", self))
        sb = QAction("Sobre o Sistema", self); sb.triggered.connect(self.mostrar_sobre)
        m4.addAction(sb)

    def _create_toolbar(self):
        tb = QToolBar("Barra de Ferramentas", self)
        tb.setIconSize(QSize(32,32))
        self.addToolBar(Qt.LeftToolBarArea, tb)
        tb.addAction(QAction(QIcon("icons/add.png"), "Novo Lançamento", self, triggered=self.novo_lancamento))
        tb.addAction(QAction(QIcon("icons/farm.png"), "Cad. Imóvel", self, triggered=lambda: self.tabs.setCurrentIndex(1)))
        tb.addAction(QAction(QIcon("icons/bank.png"), "Cad. Conta", self, triggered=lambda: self.tabs.setCurrentIndex(2)))
        tb.addAction(QAction(QIcon("icons/users.png"), "Cad. Participante", self, triggered=lambda: self.tabs.setCurrentIndex(3)))
        tb.addAction(QAction(QIcon("icons/report.png"), "Relatórios", self, triggered=lambda: self.tabs.setCurrentIndex(4)))
        tb.addAction(QAction(QIcon("icons/txt.png"), "Gerar TXT LCDPR", self, triggered=self.gerar_txt))

    def carregar_lancamentos(self):
        d1 = self.dt_ini.date().toString("yyyy-MM-dd")
        d2 = self.dt_fim.date().toString("yyyy-MM-dd")
        q = f"""
        SELECT l.id, l.data, i.nome_imovel, l.historico,
               CASE l.tipo_lanc WHEN 1 THEN 'Receita' WHEN 2 THEN 'Despesa' ELSE 'Adiantamento' END,
               l.valor_entrada, l.valor_saida,
               (l.saldo_final * CASE l.natureza_saldo WHEN 'P' THEN 1 ELSE -1 END) as saldo
        FROM lancamento l
        JOIN imovel_rural i ON l.cod_imovel=i.id
        WHERE l.data BETWEEN '{d1}' AND '{d2}'
        ORDER BY l.data DESC
        """
        rows = self.db.fetch_all(q)
        self.tab_lanc.setRowCount(len(rows))
        for r,row in enumerate(rows):
            for c,val in enumerate(row):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignCenter)
                if c==5: item.setForeground(QColor("#27ae60"))
                if c==6: item.setForeground(QColor("#e74c3c"))
                if c==7:
                    item.setForeground(QColor("#27ae60") if float(val)>=0 else QColor("#e74c3c"))
                self.tab_lanc.setItem(r,c,item)

    def editar_lancamento(self):
        row = self.tab_lanc.currentRow()
        lanc_id = int(self.tab_lanc.item(row,0).text())
        dlg = LancamentoDialog(self, lanc_id)
        if dlg.exec():
            self.carregar_lancamentos()
            self.dashboard.load_data()

    def excluir_lancamento(self):
        row = self.tab_lanc.currentRow()
        lanc_id = int(self.tab_lanc.item(row,0).text())
        ans = QMessageBox.question(self, "Confirmar Exclusão",
                                   f"Excluir lançamento ID {lanc_id}?",
                                   QMessageBox.Yes | QMessageBox.No)
        if ans == QMessageBox.Yes:
            try:
                self.db.execute_query("DELETE FROM lancamento WHERE id=?", (lanc_id,))
                QMessageBox.information(self, "Sucesso", "Lançamento excluído!")
                self.carregar_lancamentos()
                self.dashboard.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao excluir: {e}")

    def carregar_planejamento(self):
        q = """
        SELECT c.nome, a.area, a.data_plantio, a.data_colheita_estimada, a.produtividade_estimada
        FROM area_producao a
        JOIN cultura c ON a.cultura_id=c.id
        """
        rows = self.db.fetch_all(q)
        self.tab_plan.setRowCount(len(rows))
        for r,(cultura,area,pl,ce,prod) in enumerate(rows):
            self.tab_plan.setItem(r,0, QTableWidgetItem(cultura))
            self.tab_plan.setItem(r,1, QTableWidgetItem(f"{area} ha"))
            self.tab_plan.setItem(r,2, QTableWidgetItem(pl or ""))
            self.tab_plan.setItem(r,3, QTableWidgetItem(ce or ""))
            self.tab_plan.setItem(r,4, QTableWidgetItem(f"{prod}"))

    def novo_lancamento(self):
        dlg = LancamentoDialog(self)
        if dlg.exec():
            self.carregar_lancamentos()
            self.dashboard.load_data()

    def cad_imovel(self):
        self.tabs.setCurrentIndex(1)

    def cad_conta(self):
        self.tabs.setCurrentIndex(2)

    def cad_participante(self):
        self.tabs.setCurrentIndex(3)

    def exportar_dados(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar Dados", "", "CSV (*.csv)")
        if not path: return
        try:
            lancs = self.db.fetch_all("SELECT * FROM lancamento")
            with open(path,'w',newline='',encoding='utf-8') as f:
                w = csv.writer(f, delimiter=';')
                w.writerow([
                    "ID","Data","Imóvel","Conta","Documento","Tipo Doc",
                    "Histórico","Participante","Tipo","Entrada","Saída","Saldo","Natureza","Categoria"
                ])
                for l in lancs:
                    w.writerow(l[1:])
            QMessageBox.information(self, "Exportação", "Dados exportados com sucesso!")
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro na exportação: {e}")

    def gerar_txt(self):
        try:
            with open("LCDPR.txt","w",encoding='utf-8') as f:
                f.write("|0000|LCDPR|001|0001|\n")
                for im in self.db.fetch_all("SELECT * FROM imovel_rural"):
                    f.write("|0040|"+ "|".join([
                        im[1],im[2],im[3] or "",im[4] or "",im[5] or "",im[6],
                        im[7],im[8] or "",im[9] or "",im[10],im[11],im[12],
                        im[13],str(im[14]),f"{im[15]:.2f}"
                    ])+"|\n")
                for ct in self.db.fetch_all("SELECT * FROM conta_bancaria"):
                    f.write("|0050|"+ "|".join([
                        ct[1],ct[2],ct[3] or "",ct[4],ct[5],str(ct[6])
                    ])+"|\n")
                for p in self.db.fetch_all("SELECT * FROM participante"):
                    f.write("|0100|"+ "|".join([
                        p[1],p[2],str(p[3])
                    ])+"|\n")
                for l in self.db.fetch_all("SELECT * FROM lancamento"):
                    f.write("|Q100|"+ "|".join([
                        l[1],str(l[2]),str(l[3]),l[4] or "",str(l[5]),str(l[6]),
                        l[7] or "",str(l[8]),f"{l[9]:.2f}",f"{l[10]:.2f}",
                        f"{l[11]:.2f}",l[12]
                    ])+"|\n")
                f.write("|9999|1|\n")
            QMessageBox.information(self,"TXT","Arquivo LCDPR.txt gerado!")
        except Exception as e:
            QMessageBox.critical(self,"Erro",f"Erro ao gerar TXT: {e}")

    def abrir_balancete(self):
        dlg = RelatorioPeriodoDialog("Balancete", self)
        if dlg.exec():
            d1,d2 = dlg.periodo
            # lógica de balancete

    def abrir_razao(self):
        dlg = RelatorioPeriodoDialog("Razão", self)
        if dlg.exec():
            d1,d2 = dlg.periodo
            # lógica de razão

    def mostrar_sobre(self):
        QMessageBox.information(
            self, "Sobre o Sistema",
            "Sistema AgroContábil - LCDPR\n\n"
            "Versão: 2.0\n"
            "© 2023 AgroTech Solutions\n\n"
            "Funcionalidades:\n"
            "- Gestão de propriedades rurais\n"
            "- Controle financeiro completo\n"
            "- Planejamento de safras\n"
            "- Gerenciamento de estoque\n"
            "- Geração do LCDPR"
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
