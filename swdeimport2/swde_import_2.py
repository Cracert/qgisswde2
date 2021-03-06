# -*- coding: utf-8 -*-
"""
/***************************************************************************
 SWDEImport2
                                 A QGIS plugin
 importuje dane z plików SWDE do bazy Postgis
                              -------------------
        begin                : 2015-10-20
        git sha              : $Format:%H$
        copyright            : (C) 2015 by Robert Dorna
        email                : robert.dorna@wp.eu
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
#from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
#from PyQt4.QtGui import QAction, QIcon

# Import the PyQt and QGIS libraries
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsPoint
# Initialize Qt resources from file resources.py
import resources_rc
# Import the code for the dialog
from swde_import_2_dialog import SWDEImport2Dialog
import os.path

from rob_db_connection import RobDBBase
from rob_db_connection import RobDBTable
#from swde_to_postgis_class import SwdeToPostgis

#from createpostgisswdedb import CreatePostgisSwdeDb
from datetime import datetime
import time
import unicodedata
import sys

#from subprocess import Popen, PIPE, call


#import rpdb2; rpdb2.start_embedded_debugger('haslo')#tylko na potrzeby debugowania z winpdb

class SWDEImport2:
    """QGIS Plugin Implementation."""
    swde_file = ""
    plik_data = "" 
    ilosc_linii = ""
    pzgdic = {}
    pguser = ""
    pgbase = ""
    pguserpswd = ""
    pgserver = ""
    pgport = ""
    pgadmin = ""
    pgadminpswd = ""
    tmppath = ""
    ogr2ogrpath = ""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'SWDEImport2_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = SWDEImport2Dialog()
        
        
        #dane startowe
        self.swde_file = "" #nazwa pliku - pełna ścieżka - string
        self.f = 0          #obiekt typu file o ścieżce self.swde_file
        


        #dane dotyczace serwera odczytane z QSettings
        sett = QSettings('erdeproj', 'SWDE_qgis_plugin')
        self.pguser = sett.value('pguser', '', type=str)
        self.pgbase = sett.value('pgbase', '', type=str)
        self.pguserpswd = sett.value('pguserpswd', '', type=str)
        self.pgserver = sett.value('pgserver', '', type=str)
        self.pgport = sett.value('pgport', '5432', type=str)
        self.pgadmin = sett.value('pgadmin', '', type=str)
        self.pgadminpswd = sett.value('pgadminpswd', '', type=str)
        self.tmppath = sett.value('tmppath', '', type=str)
        self.ogr2ogrpath = sett.value('ogr2ogrpath', '', type=str)
        self.terminal_command = sett.value('terminal_command', 'xterm -e', type=str)
        self.terminal_file_separator = sett.value('terminal_file_separator', '', type=str)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&SWDE Import v2')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'SWDEImport2')
        self.toolbar.setObjectName(u'SWDEImport2')

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('SWDEImport2', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToDatabaseMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/SWDEImport2/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Import danych SWDE'),
            callback=self.run,
            parent=self.iface.mainWindow())
            
        self.connGuiSignals()#łączenie sygnałów z obiektami z GUI    
            
        #ustawienie wartosci editow z zakladki ustawienia bazy danych
        self.dlg.leditDBServer.setText(self.pgserver)
        self.dlg.leditDBBaseName.setText(self.pgbase)
        self.dlg.leditDBUser.setText(self.pguser)
        self.dlg.leditDBPassword.setText(self.pguserpswd)
        
        #inicializacja tablicy items dla combobox z ukladami przestrzennymi
        self.cmb_pyproj4_items = {}
        try:
            pyproj4file = self.plugin_dir + u"/pyproj4str"
            f = open(pyproj4file, "r")
            try:
                second = 0
                key = ""
                value = ""
                for line in f.readlines():
                    line = line.rstrip('\n')
                    line = line.rstrip('\r')
                    if second == 0:
                        key = line
                        second = 1
                    else:
                        value = line
                        self.cmb_pyproj4_items [key] = value 
                        self.dlg.cmbPyprojFrom.addItem(key, value)
                        self.dlg.cmbPyprojTo.addItem(key, value)
                        second = 0

            finally:
                f.close()
        except IOError:
            self.dlg.peditOutput.appendPlainText("error: " + pyproj4file)
            pass



    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginDatabaseMenu(
                self.tr(u'&SWDE Import v2'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar


    def run(self):
        """Run method that performs all the real work"""
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass
            
    def connGuiSignals(self):
        #========Zakładka import===========
        #--------buttons
        QObject.connect(self.dlg.tbtnWybierzSWDEFile,SIGNAL("clicked()"),self.tbtnWybierzSWDEFileClicked)
        QObject.connect(self.dlg.pbtnSWDEHeaderInfo,SIGNAL("clicked()"),self.pbtnSWDEHeaderInfoClicked)
        QObject.connect(self.dlg.pbtnSWDEHeaderFull,SIGNAL("clicked()"),self.pbtnSWDEHeaderFullClicked)
        QObject.connect(self.dlg.pbtnImportuj,SIGNAL("clicked()"),self.pbtnImportujClicked)
        QObject.connect(self.dlg.pbtnDBSaveSettings,SIGNAL("clicked()"),self.pbtnDBSaveSettingsClicked)
        QObject.connect(self.dlg.tbtnTmpFolder,SIGNAL("clicked()"),self.tbtnTmpFolderClicked)
        QObject.connect(self.dlg.tbtnOgr2ogrFile,SIGNAL("clicked()"),self.tbtnOgr2ogrFileClicked)

        #--------edits and labels

        #--------checkboxes and radiobuttons
        
############################################################################# 
###          funkcje interfejsu, przyciski itp....                        ###
############################################################################

#---------------------------------------------------------------------------#        
    def tbtnWybierzSWDEFileClicked(self):
        self.swde_file = QFileDialog.getOpenFileName(self.dlg, 'Wybierz plik SWDE', '.')
        self.dlg.leditSWDEFile.setText(self.swde_file)
          
#-----------------------------------------------------------------------------------#
    def pbtnSWDEHeaderInfoClicked(self):

        self.dlg.peditSWDEHeader.clear()
        self.dlg.peditOutput.appendPlainText("Start: " +  time.strftime("%Y-%m-%d %H:%M:%S"))
        try:
            #f = open(str(self.swde_file.toUtf8()).decode('utf-8'), "r")
            f = open(self.swde_file, "r")
            try:
                i = 0 #licznik linii - nie ma sensu wczytywac całego pliku
                txt = ''
                for line in f.readlines():

                    #pocz = line[0:2]
                    pocz = StringBetweenChar(line, ',',0)
                    #print i, pocz
                    rodz_info = ""
                    opis = ""
                    opis_info = ""
                    i+=1
                    if pocz == "NS":
                        line = line.rstrip('\r')
                        line = line.rstrip('\n')
                        rodz_info = StringBetweenChar(line, ',',1)

                        #opis_info = unicodedata.normalize('NFKD',opis_info).decode('ascii', 'replace')
                        #opis_info = replacePlChars(StringBetweenChar(line, ',',2))
                        opis_info = unicode( StringBetweenChar(line, ',',2), self.txtCodec(), 'replace')

                        if rodz_info == u"DN":
                            opis = u"Data utworzenia pliku: "
                        elif rodz_info == u"TR":
                            opis = u"Nr identyfikacyjny jednostki tworzącej plik: "
                        elif rodz_info == u"TN":
                            opis = u"Nazwa jednostki tworzącej plik: "
                        elif rodz_info == u"TA":
                            opis = u"Adres jednostki tworzącej plik: "
                        elif rodz_info == u"TO":
                            opis = u"Imię i nazwisko wykonawcy: "
                        elif rodz_info == u"ZN":
                            opis = u"Nazwa systemu - źródła danych: "
                        elif rodz_info == u"ZR":
                            opis = u"Nr identyfikacyjny systemu - źródła danych: "
                        elif rodz_info == u"ZD":
                            opis = u"Nazwa zbioru danych - reprezentowanego obiektu: "
                        elif rodz_info == u"OP":
                            opis = u"Przeznaczenie danych: "
                        elif rodz_info == u"OR":
                            opis = u"Nr identyfikacyjny jednostki przeznaczenia: "
                        elif rodz_info == u"ON":
                            opis = u"Nazwa jednostki przeznaczenia: "
                        elif rodz_info == u"OA":
                            opis = u"Adres jednostki przeznaczenia: "
                        elif rodz_info == u"OO":
                            opis = u"Imię i nazwisko odbiorcy: "
                        elif rodz_info == u"UX":
                            opis = u"Nazwa układu współrzędnych: "
                        elif rodz_info == u"OS":
                            opis = u"Nazwa / numer strefy odwzorowania: "
                        elif rodz_info == u"NX":
                            opis = u"Nazwa pierwszej współrzędnej : "
                        elif rodz_info == u"NY":
                            opis = u"Nazwa drugiej wspolrzednej: "
                        elif rodz_info == u"NZ":
                            opis = u"Nazwa trzeciej wspolrzednej : "
                        elif rodz_info == u"UH":
                            opis = u"System wysokosci : "
                        elif rodz_info == u"HZ":
                            opis = u"Poziom odniesienia : "

                        txt += u"<b>" + rodz_info + u"</b>  - " + opis + opis_info + u"<br>"
                    
                    if i == 100:
                        break
                self.dlg.peditSWDEHeader.setText(txt)
                    

            finally:
                txt = 'Plik zamkniety: ' + time.strftime("%Y-%m-%d %H:%M:%S")
                self.dlg.peditOutput.appendPlainText(txt)
                f.close()
        
        except IOError:
            self.dlg.peditOutput.appendPlainText("IOError:" +  time.strftime("%Y-%m-%d %H:%M:%S"))
            pass
            
#------------------------------------------------------------------------#
    def pbtnSWDEHeaderFullClicked(self):
        self.dlg.peditSWDEHeader.clear()
        self.dlg.peditOutput.appendPlainText("Start: " +  time.strftime("%Y-%m-%d %H:%M:%S"))
        txtcodec = self.txtCodec()
        try:
            #f = open(str(self.swde_file.toUtf8()).decode('utf-8'), "r")
            f = open(self.swde_file, "r")
            try:
                i = 0 #licznik linii - nie ma sensu wczytywac całego pliku
                txt = ''
                for line in f.readlines():
                    i+=1
                    txt += unicode(line, txtcodec, 'replace')


                    if i == 1000:
                        break
                self.dlg.peditSWDEHeader.setText(txt) 

            finally:
                txt = 'Plik zamkniety: ' + time.strftime("%Y-%m-%d %H:%M:%S")
                self.dlg.peditOutput.appendPlainText(txt)
                f.close()
        
        except IOError:
            self.dlg.peditOutput.appendPlainText("IOError:" +  time.strftime("%Y-%m-%d %H:%M:%S"))
            pass


#------------------------------------------------------------------------------------#
    def pbtnDBSaveSettingsClicked(self):
        sett = QSettings('erdeproj', 'SWDE_qgis_plugin')
        self.pgserver = self.dlg.leditDBServer.displayText()
        self.pgbase = self.dlg.leditDBBaseName.displayText()
        self.pguser = self.dlg.leditDBUser.displayText()
        self.pguserpswd = self.dlg.leditDBPassword.text()
        self.pgport = self.dlg.leditDBPort.text()
        sett.setValue('pguser', self.pguser)
        sett.setValue('pgbase', self.pgbase)
        sett.setValue('pguserpswd', self.pguserpswd)
        sett.setValue('pgserver', self.pgserver)
        sett.setValue('pgport', self.pgport)
        
#---------------------------------------------------------------------------------------#        
    def tbtnTmpFolderClicked(self):
        sett = QSettings('erdeproj', 'SWDE_qgis_plugin')
        self.tmppath = QFileDialog.getExistingDirectory(self.dlg, u'Wybierz lokalizację folderu plików tymczasowych', '.', QFileDialog.ShowDirsOnly)
        sett.setValue('tmppath', self.tmppath)
        self.dlg.leditTmpFolder.setText(self.tmppath)
#----------------------------------------------------------------------------------------#
    def pbtnImportujClicked(self):
        #do czasu calkowitego rozwiazania problemu, funkcja zostaje nieaktywna   

        
        tableList = ""
        
        
        if self.dlg.chckG5dze.isChecked():
            tableList = tableList + 'G5DZE'
        if self.dlg.chckG5obr.isChecked():
            tableList = tableList + ',G5OBR'
        if self.dlg.chckG5jew.isChecked():
            tableList = tableList + ',G5JEW'
        if self.dlg.chckG5jdr.isChecked():
            tableList = tableList + ',G5JDR'
        if self.dlg.chckG5adr.isChecked():
            tableList = tableList + ',G5ADR'    
        if self.dlg.chckG5dze.isChecked():
            tableList = tableList + ',G5DZE'    
        if self.dlg.chckG5udz.isChecked():
            tableList = tableList + ',G5UDZ'
        if self.dlg.chckG5udw.isChecked():
            tableList = tableList + ',G5UDW'
        if self.dlg.chckG5osf.isChecked():
            tableList = tableList + ',G5OSF'
        if self.dlg.chckG5ins.isChecked():
            tableList = tableList + ',G5INS'
        if self.dlg.chckG5mlz.isChecked():
            tableList = tableList + ',G5MLZ'
        if self.dlg.chckG5osz.isChecked():
            tableList = tableList + ',G5OSZ'
        if self.dlg.chckG5klu.isChecked():
            tableList = tableList + ',G5KLU'
        if self.dlg.chckG5uzg.isChecked():
            tableList = tableList + ',G5UZG'
        if self.dlg.chckG5dok.isChecked():
            tableList = tableList + ',G5DOK'
        if self.dlg.chckG5bud.isChecked():
            tableList = tableList + ',G5BUD'
        if self.dlg.chckG5lkl.isChecked():
            tableList = tableList + ',G5LKL'
        if self.dlg.chckG5zmn.isChecked():
            tableList = tableList + ',G5ZMN'
        if self.dlg.chckG5kkl.isChecked():
            tableList = tableList + ',G5KKL'
        if self.dlg.chckG5zmn.isChecked():
            tableList = tableList + ',G5ZMN'
            
        
        srid = str(self.dlg.leditSRIDImport.text())
        if srid == '':
            srid = 'NONE'   
        
        pyproj4strFrom = self.cmb_pyproj4_items[self.dlg.cmbPyprojFrom.currentText()]
        pyproj4strTo = self.cmb_pyproj4_items[self.dlg.cmbPyprojTo.currentText()]        
        
        rodz_importu = ''
        
        if self.dlg.rdbtnZwyklyImport.isChecked():
            rodz_importu = 'zwykly'
        elif self.dlg.rdbtnAktualizacja.isChecked():
            rodz_importu = 'aktualizacja'
        elif self.dlg.rdbtnUzupelnienieOpis.isChecked():
            rodz_importu = 'uz_opis'
        elif self.dlg.rdbtnImportTestowy.isChecked():
            if self.dlg.rdbtnTestowyJEW.isChecked():
                rodz_importu = 'testowyJEW'
            elif self.dlg.rdbtnTestowyOBR.isChecked():
                rodz_importu = 'testowyOBR'
            elif self.dlg.rdbtnTestowyDZE.isChecked():
                rodz_importu = 'testowyDZE'
        
        
        #parametry do polaczenia z baza
        pgserver = self.pgserver
        pgbase = self.pgbase
        pguser = self.pguser
        pguserpswd = self.pguserpswd
        
        txtcodec = ''
        if self.dlg.rdbtnKodowanieISO.isChecked():
            txtcodec =  'iso8859_2'
        elif self.dlg.rdbtnKodowanieWindows.isChecked():
            txtcodec = 'cp1250'
        elif self.dlg.rdbtnKodowanieUTF.isChecked():
            txtcodec = 'utf-8'
                  
        
        id_jed_rej =  self.dlg.leditIDZD.text() 
        id_jed_rej  = str(id_jed_rej).rstrip()
        if id_jed_rej == '':
            id_jed_rej = 'NONE'
            
        self.SwdeToPostgis(self.swde_file, tableList, srid, pyproj4strFrom, pyproj4strTo, rodz_importu, pgserver, pgbase, pguser, pguserpswd, txtcodec, id_jed_rej)
 
#-------------------------------------------------------------------------------#
    def SwdeToPostgis(self, swde_file, tableListString, srid, pyproj4strFrom, pyproj4strTo, rodz_importu, pgserver, pgbase, pguser, pguserpswd, txtcodec, id_jed_rej):
        
        #TODO przewidziec pominiecie tego kroku podczas importu uzupełniającego danych opisowych
        uni = lambda s: s if type(s) == unicode else unicode(s,'utf-8','replace')
        #....................zczęść odpowiedzialna za pzg.......................
        ##wypelnienie struktury słownikowej z rozwinięciami punktów granicznych
        pzgdic = {}
    
        uz_opis = False
        if rodz_importu == 'uz_opis':
            uz_opis = True
       
        ilosc_pzg = 0
        dze_g5idd = '' #specjalna wartosc, identyfikator dzialki w tabeli dzialek - wykorzystywane tylko w przypadku uzupelniania danych opisowych
            #czyli rodz_umportu uz_opis
        dic_idx = ""
        rp = 0
        ile_lini_step = 0 #liczba linii w poszczególnym kroku - pomocne przy wyrzucaniu informacji o aktualnym
        #procesie postępu zadania
        step = 100000
        ilosc_linii = 0 #calkowita ilosc linii w pliku
        id_jr = "" #id jednostki rejestrowej wyluskana z pliku
        self.dlg.peditOutput.appendPlainText((u"Import rozpoczęty: " +   time.strftime("%Y-%m-%d %H:%M:%S")))
        QApplication.processEvents()
        if swde_file != '':
            print "jeden"
            
            pgv = 0
            
            #znaczniki dla zobrazowania pracy w konsoli
            znacznik = ["/","-","\\","|"]
            zn_nr = 0
            try:
                #self.f = open(str(self.swde_file.toUtf8()).decode('utf-8'), "r")
                f = open(swde_file, "r")
                self.dlg.peditOutput.appendPlainText(( "Plik" + uni(swde_file) + "otwarty do odczytu: " + time.strftime("%Y-%m-%d %H:%M:%S")))
                if uz_opis:
                    self.dlg.peditOutput.appendPlainText("wyszukiwanie identyfikatora jednostki rejestrowej:  /")
                else:
                    self.dlg.peditOutput.appendPlainText("analiza PZG:  /")
                QApplication.processEvents()
                try:
                    for line in f.readlines():
                        ilosc_linii+=1
                        ile_lini_step+=1
                        if StringBetweenChar(line, ',', 0) == "NS" and StringBetweenChar(line, ',', 1) == "ZD":
                            id_jr = StringBetweenChar(line, ',', 2)
                            if uz_opis:
                                break

                        if StringBetweenChar(line, ',',1) == "DN":
                            self.plik_data =  StringBetweenChar(line, ',',2)
                            self.dlg.peditOutput.appendPlainText( u"Plik SWDE z dnia --  " + uni(self.plik_data))

                        pocz = StringBetweenChar(line, ',',0)        
                        if pocz == "RP":
                            tab = StringBetweenChar(line, ',',2)
                            if tab == "G5PZG":
                                nr = StringBetweenChar(line, ',', 3)
                                rp = 1
                                dic_idx = nr
                        elif rp == 1:
                            y =StringBetweenChar(line, ',', 2)
                            x =StringBetweenChar(line, ',', 3)
                            dic_value = y +"," + x
                            pzgdic[nr] = dic_value
                            rp = 0
                            ilosc_pzg += 1
                        if ile_lini_step == step:  
                            curs = self.dlg.peditOutput.textCursor()
                            curs.clearSelection()
                            curs.movePosition(QTextCursor.PreviousCharacter, QTextCursor.KeepAnchor)
                            curs.insertText(znacznik[zn_nr])
                            QApplication.processEvents()
                            
                            if zn_nr == 3:
                                zn_nr = 0
                            else:    
                                zn_nr = zn_nr+1
                            ile_lini_step = 0
    
    
                finally:
                    self.dlg.peditOutput.appendPlainText( "zakonczono" + time.strftime("%Y-%m-%d %H:%M:%S"))
                    f.close()
                    self.dlg.peditOutput.appendPlainText( "plik zamkniety" + time.strftime("%Y-%m-%d %H:%M:%S"))
                    self.dlg.peditOutput.appendPlainText( "ilosc linii pliku: "+ str(ilosc_linii))
        
                    self.dlg.peditOutput.appendPlainText( "ilosc puntkow zalamania granicy: " + str(ilosc_pzg))
                    id_jr = id_jr.strip()
                    if id_jr !="":
                        self.dlg.peditOutput.appendPlainText( "Znaleziony identyfikator jednostki rejestrowej: " +  uni(id_jr) +  u" zostanie wykorzystany  w bazie do stworzenia kluczy obiektów. Jeśli chcesz użyć innego możesz go zastąpić wpisanym przez siebie tekstem")
                    elif id_jed_rej=="":
                        self.dlg.peditOutput.appendPlainText( u"Nie znaleziono identyfikatora jednostki rejestrowej - musisz samodzielnie określić identyfikator zbioru danych, wpisując samodzielnie - litery i cyfry - najlepiej do 10 znaków. Nie używaj polskich liter")
                        QMessageBox.information(self.dlg, "Uwaga!!!", u"Nie znaleziono identyfikatora jednostki rejestrowej - musisz samodzielnie określić identyfikator zbioru danych, wpisując samodzielnie - litery i cyfry - najlepiej do 10 znaków. Nie używaj polskich liter")
                        return 0
    
            except IOError:
                self.dlg.peditOutput.appendPlainText( u"IOError: błąd wczytania pliku swde")
                
        #........................................................................
        #.....część odpowiedzialna za import....................................
        crs_source = QgsCoordinateReferenceSystem()
        crs_source.createFromProj4(str(pyproj4strFrom))
        crs_dest = QgsCoordinateReferenceSystem()
        crs_dest.createFromProj4(str(pyproj4strTo))
        xform = QgsCoordinateTransform(crs_source, crs_dest)
        
        
        tableList = [] #tabela nazw tabel w bazie
        grafTableList = [] #nazwy tabel z grafiką w bazie
        
        
        import_testowy = False
        if rodz_importu == 'testowyJEW' or rodz_importu == 'testowyOBR' or rodz_importu == 'testowyDZE':
            import_testowy = True
        
        try:
            f = open(swde_file, "r")
            if f == 0 or f.closed:
                self.dlg.peditOutput.appendPlainText( u"Przed rozpoczęciem importu musisz wczytać plik")
            else:
                if id_jed_rej == 'NONE': #parametr wybierany przez uzytkownika, jesli jest inny niz NONE
                    id_jed_rej  = str(id_jr).rstrip() #zostanie uzyty jako wymuszenie nazwy zbioru danych
                
                #lista column tablicowych - do innej obróbki niż pozostałe
                arrayCols = ['G5RADR', 'G5RPWL', 'G5RPWD', 'G5RKRG', 'G5RSKD', 'G5RDOK', 'G5RDZE', 'G5ROBJ']
                #słownik kolumn do zmiany nazwy - zmieniamy polskie znaki w nazwie kolumn bo trochę to broi przy pytaniach SQL
                plcharCols =  {u'G5RŻONA':'G5RZONA', u'G5RMĄŻ':'G5RMAZ', u'G5RPWŁ':'G5RPWL', u'G5RWŁ':'G5RWL', u'G5RWŁS':'G5RWLS', u'G5RWŁD':'G5RWLD'}
                g5Cols = {} #słownik zbudowany: {'nazwa_tabeli':Tablica_Column[]} - posluzy do inicjacji tabel - obiektow robdbtable 
                #inicjalizacja  bazy danych
					#wartosc przekraczajaca przewdidziana dlugosc wartosci w bazie, jako zabezpieczenie przed bledem 'to long value...'
                rdbase = RobDBBase(pgserver, pgbase, pguser, pguserpswd,1)
                rdg5Table = {}  #słownik zawiera następującą strukturę: {'nazwa_tabeli': Obiekt_rdbtable}
                
                #colsLen = {} #slownik zbudowany: {'nazwa_tabeli':{'nazwa_kolumny':dlugosc}} - posluzy do sprawdzania czy do bazy nie zostanie zapisana
                colsLen = {'G5ADR':{'TAB_UID':50,  'G5TAR':1,  'G5NAZ':150,  'G5KRJ':100,  'G5WJD':100,  'G5PWJ':100,  'G5GMN': 100,  'G5ULC': 255,  'G5NRA':50,  'G5NRL': 50,  'G5MSC':100,  'G5KOD':50,  'G5PCZ': 100,  'G5DTW':25,  'G5DTU':25,  'ID_ZD':50,  'G5ID2':50,  'G5ID1':50},    'G5BUD':{'TAB_UID':50,  'G5IDB':50,   'G5FUZ':2,   'G5DWR':20,   'G5RZN':50,   'G5SCN':1,   'G5RADR':50,  'G5RPWL':50,  'G5RPWD':50,  'G5RKRG':50,  'G5RJDR':50,  'G5RDZE':50,  'G5DTW':25,  'G5DTU':25,   'ID_ZD':50 ,  'G5ID2':50,  'G5ID1':50  },    'G5DOK':{  'TAB_UID':50,  'G5KDK':10,  'G5DTD':25,  'G5DTP':25,  'G5SYG':255,  'G5NSR':255,  'G5RDOK':50,  'G5DTW':25,   'G5DTU':25,   'ID_ZD':40,   'G5ID2':50,  'G5ID1':50,  },  'G5DZE':{ 'G5IDD':40,  'NR':20,  'ID_ZD':50,  'G5IDR':100,  'G5NOS':100,  'G5WRT':20,  'G5DWR':25,  'G5RZN':100,  'G5DWW':25,  'G5RADR':50,  'G5RPWL':50,  'G5RPWD':50,  'G5RJDR':50,  'G5DTW':25,  'G5DTU':25,   'G5RKRG':50,  'G5ID2':50,  'G5ID1':50,  'NROBR':10,  'TAB_UID':50  },    'G5DZE_TEST':{ 'G5IDD':40,  'NR':20,  'ID_ZD':50,  'G5IDR':100,  'G5NOS':100,  'G5WRT':20,  'G5DWR':25,  'G5RZN':100,  'G5DWW':25,  'G5RADR':50,  'G5RPWL':50,  'G5RPWD':50,  'G5RJDR':50,  'G5DTW':25,  'G5DTU':25,   'G5RKRG':50,  'G5ID2':50,  'G5ID1':50,  'NROBR':10,  'TAB_UID':50  },    'G5INS':{  'G5STI':2,   'G5NPE':255,  'G5NSK':255,   'G5RGN':20,  'G5NIP':20,  'G5NZR':100,  'G5NRR':50,  'G5NSR':255,  'G5RADR':50,  'G5DTW':25,  'G5DTU':25,   'ID_ZD':40,  'G5ID2':50,  'G5ID1':50,  'TAB_UID':50  },    'G5JDR':{  'G5TJR': 1,  'G5IJR':50,  'G5RGN':20,  'G5RWL':1,  'G5RWLS':50,  'G5RWLD':50,  'G5ROBR':50,  'G5DTW':25,  'G5DTU':25,  'ID_ZD':40,  'G5ID2':50,  'G5ID1':50,  'TAB_UID':50  },  'G5JEW':{  'G5IDJ':20,  'G5NAZ':50,  'G5DTW':25,  'G5DTU':25,  'G5RKRG':20,  'ID_ZD':50,  'G5ID2':50,  'G5ID1':50,  'TAB_UID':50  },  'G5JEW_TEST':{  'G5IDJ':20,  'G5NAZ':50,  'G5DTW':25,  'G5DTU':25,  'G5RKRG':20,  'ID_ZD':50,  'G5ID2':50,  'G5ID1':50,  'TAB_UID':50  },  'G5KKL':{  'TAB_UID':50,  'G5IDK':50,  'G5OZU':10,  'G5OZK':10,  'G5RKRG':50,  'G5ROBR':50,  'G5DTW':25,  'G5DTU':25,  'ID_ZD':40,  'G5ID2':50,  'G5ID1':50  },  'G5KLU':{  'G5OFU':10,  'G5OZU':10,  'G5OZK':5,  'G5RDZE':50,  'G5DTW':25,  'G5DTU':25,  'ID_ZD':40,  'G5ID2':50,  'G5ID1':50,  'TAB_UID':50  },  'G5LKL':{  'TAB_UID':50 ,  'G5IDL':50,   'G5TLOK':1, 'G5DWR':25,   'G5RJDR':50,   'G5RADR':50,   'G5RDOK':50,   'G5RBUD':50,   'G5DTW':25,   'G5DTU':25,   'ID_ZD':40 ,   'G5ID2':50,   'G5ID1':50  },  'G5MLZ':{  'G5DTW':25,   'G5DTU':25,   'ID_ZD':40 ,   'G5ID2':50,   'G5RMAZ':50,  'G5RZONA':50,  'G5ID1':50,  'TAB_UID':50},  'G5OBR':{  'G5NRO':40 ,   'G5NAZ':50,   'G5DTW':25,  'G5DTU':25,  'G5RKRG':20,  'G5RJEW': 20,  'ID_ZD':40 ,   'G5ID2':50,   'G5ID1':50,  'TAB_UID':50 ,   'IDJEW':50},  'G5OBR_TEST':{  'G5NRO':40 ,   'G5NAZ':50,   'G5DTW':25,  'G5DTU':25,  'G5RKRG':20,  'G5RJEW': 20,  'ID_ZD':40 ,   'G5ID2':50,   'G5ID1':50,  'TAB_UID':50 ,   'IDJEW':50},  'G5OSF':{  'G5PLC':1,   'G5PSL':15,  'G5NIP':20,   'G5NZW':100,   'G5PIM':50,   'G5DIM':50,   'G5OIM':50,   'G5MIM':50,   'G5OBL':50,   'G5DOS':50,   'G5RADR':50,   'G5STI': 1,  'G5DTW':25,  'G5DTU':25,   'ID_ZD':40 ,   'G5ID2':50,   'G5ID1':50 ,  'TAB_UID':50} ,  'G5OSZ':{  'G5STI': 2,   'G5NPE':255,   'G5NSK':255,   'G5RGN':20,  'G5NIP':20,  'G5RADR':50,  'G5DTW':25,   'G5DTU':25,   'ID_ZD':40 ,   'G5ID2':50,   'G5ID1':50,  'G5RSKD':50,  'TAB_UID':50} ,  'G5UDW':{  'G5RWD': 1,   'G5UD':50,   'G5RWLD':50,   'G5RPOD':50,   'G5DTW':25,   'G5DTU':25,   'ID_ZD':40 ,   'G5ID2':50,   'G5ID1':50,   'RPOD_RODZAJ':20,  'ID_PODMIOT':50,   'TAB_UID':50} ,  'G5UDZ':{  'G5UD':50,   'G5RWLS':50,   'G5RPOD':50,   'G5DTW':25,   'G5DTU':25,   'ID_ZD':40 ,   'G5ID2':50,   'G5ID1':50,  'RPOD_RODZAJ':20,  'ID_PODMIOT':50,   'G5UDZ_URPOD':50,   'TAB_UID':50},   'G5UZG':{  'G5IDT':50,   'G5OZU':10,   'G5RKRG':50,   'G5ROBR':50,   'G5DTW':25,   'G5DTU':25,   'ID_ZD':40 ,   'G5ID2':50,   'G5ID1':50,   'G5OFU':10,  'TAB_UID':50} ,  'G5ZMN':{  'TAB_UID':50 ,  'G5NRZ':50,   'G5STZ':255,   'G5DZZ':25,   'G5DTA':25,   'G5DTZ':25,   'G5NAZ':255,   'G5ROBJ':50,   'G5RDOK':50,   'G5DTW':25,   'G5DTU':25,   'ID_ZD':40 ,   'G5ID2':50,   'G5ID1':50}}
                #OKRESLENIe rodzaju importu
                
                self.dlg.peditOutput.appendPlainText("rodzaj importu : " + rodz_importu)
                
                if rodz_importu == 'zwykly' or rodz_importu == 'aktualizacja' or rodz_importu == 'uz_opis':
                    Cols = ['G5IDJ', 'G5PEW', 'G5NAZ', 'G5DTW', 'G5DTU','G5RKRG']#g5jew
                    g5Cols['G5JEW'] = Cols
                    Cols = [ 'G5IDD',  'GEOM',    'NR', 'G5IDR', 'G5NOS', 'G5WRT', 'G5DWR', 'G5PEW', 'G5RZN', 'G5DWW', 'G5RADR', 'G5RPWL', 'G5RPWD', 'G5RKRG', 'G5RJDR', 'G5DTW', 'G5DTU'] #g5dze
                    g5Cols['G5DZE'] = Cols
                    Cols = [ 'G5NRO', 'G5PEW', 'G5NAZ', 'G5DTW', 'G5DTU', 'G5RKRG', 'G5RJEW', 'IDJEW'] #g5obr
                    g5Cols['G5OBR'] = Cols
                    Cols = ['G5PLC', 'G5PSL', 'G5NIP', 'G5NZW', 'G5PIM', 'G5DIM', 'G5OIM', 'G5MIM', 'G5OBL', 'G5DOS', 'G5RADR', 'G5STI', 'G5DTW', 'G5DTU'] #g5osf
                    g5Cols['G5OSF'] = Cols
                    Cols = [ 'G5STI', 'G5NPE', 'G5NSK', 'G5RGN', 'G5NIP', 'G5NZR', 'G5NRR', 'G5NSR', 'G5RADR', 'G5DTW', 'G5DTU'] #g5ins
                    g5Cols['G5INS'] = Cols
                    Cols = ['G5RZONA',  'G5RMAZ', 'G5DTW', 'G5DTU'] #g5mlz
                    g5Cols['G5MLZ'] = Cols
                    Cols = [ 'G5STI', 'G5NPE', 'G5NSK', 'G5RGN', 'G5NIP', 'G5RSKD', 'G5RADR', 'G5DTW', 'G5DTU'] #g5osz
                    g5Cols['G5OSZ'] = Cols
                    Cols = ['G5TJR', 'G5IJR', 'G5RGN', 'G5RWL', 'G5RWLS', 'G5RWLD', 'G5ROBR', 'G5DTW', 'G5DTU' ] #g5jdr
                    g5Cols['G5JDR'] = Cols
                    Cols = [ 'G5UD', 'G5RWLS', 'G5RPOD', 'G5DTW', 'G5DTU'] #g5udz
                    g5Cols['G5UDZ'] = Cols
                    Cols = [ 'G5RWD', 'G5UD', 'G5RWLD', 'G5RPOD', 'G5DTW', 'G5DTU'] #g5udw
                    g5Cols['G5UDW'] = Cols
                    Cols = [ 'G5OFU', 'G5OZU', 'G5OZK', 'G5PEW', 'G5RDZE', 'G5DTW', 'G5DTU'] #g5klu
                    g5Cols['G5KLU'] = Cols
                    Cols = [ 'G5IDT', 'G5OZU','G5OFU', 'G5PEW', 'G5RKRG', 'G5ROBR', 'G5DTW', 'G5DTU'] #g5uzg
                    g5Cols['G5UZG'] = Cols
                    Cols = ['G5KDK', 'G5DTD', 'G5DTP', 'G5SYG', 'G5NSR', 'G5OPD', 'G5RDOK', 'G5DTW', 'G5DTU'] #g5dok
                    g5Cols['G5DOK'] = Cols
                    Cols = ['G5TAR', 'G5NAZ', 'G5KRJ', 'G5WJD', 'G5PWJ', 'G5GMN', 'G5ULC', 'G5NRA', 'G5NRL', 'G5MSC', 'G5KOD', 'G5PCZ', 'G5DTW', 'G5DTU']#g5adr
                    g5Cols['G5ADR'] = Cols
                    Cols = ['G5IDB', 'G5FUZ', 'G5WRT', 'G5DWR', 'G5RBB', 'G5PEW', 'G5PEU', 'G5RZN', 'G5SCN', 'G5RADR', 'G5RPWL', 'G5RPWD', 'G5RKRG', 'G5RJDR','G5RDZE', 'G5DTU', 'G5DTW']#g5bud
                    g5Cols['G5BUD'] = Cols
                    Cols = ['G5IDK', 'G5OZU', 'G5OZK', 'G5PEW', 'G5RKRG', 'G5ROBR', 'G5DTW', 'G5DTU']
                    g5Cols['G5KKL'] = Cols
                    Cols = ['G5IDL', 'G5TLOK', 'G5PEW', 'G5PPP', 'G5LIZ', 'G5WRT', 'G5DWR', 'G5RJDR', 'G5RADR', 'G5RDOK', 'G5RBUD', 'G5DTW', 'G5DTU']
                    g5Cols['G5LKL'] = Cols
                    Cols = ['G5NRZ', 'G5STZ', 'G5DZZ', 'G5DTA', 'G5DTZ', 'G5NAZ', 'G5ROBJ', 'G5RDOK', 'G5DTW', 'G5DTU']
                    g5Cols['G5ZMN'] = Cols
         
                    tableList = tableListString.split(',')
                    grafTableList.append('G5DZE')
         
                elif rodz_importu == 'testowyJEW' or rodz_importu == 'testowyOBR' or rodz_importu == 'testowyDZE':
                    #teoretycznie powinno wystarczyć zwykle elif bez parametrow, ale na wszelki dorzuce te ory
                    #w przypadku importu testowego importować będziemy tylko jedną z trzech tabel (dze, obr, lub jew)
                    # przy okazji opróżnimy zawartość dotychczasowych tabel testowych
                    delSQLstr = "delete from "
                    if rodz_importu == 'testowyJEW':
                        tableList.append('G5JEW')
                        g5Cols['G5JEW'] = ['G5IDJ', 'G5PEW', 'G5NAZ', 'G5DTW', 'G5DTU','G5RKRG']#g5jew
                        delSQLstr += "g5jew_test;"
                    elif rodz_importu == 'testowyOBR':
                        tableList.append('G5OBR')
                        g5Cols['G5OBR'] = [ 'G5NRO', 'G5PEW', 'G5NAZ', 'G5DTW', 'G5DTU', 'G5RKRG', 'G5RJEW', 'IDJEW']
                        delSQLstr += "g5obr_test;"
                    elif rodz_importu == 'testowyDZE':
                        tableList.append('G5DZE')
                        g5Cols['G5DZE'] = [ 'G5IDD',  'GEOM',    'NR', 'G5IDR', 'G5NOS', 'G5WRT', 'G5DWR', 'G5PEW', 'G5RZN', 'G5DWW', 'G5RADR', 'G5RPWL', 'G5RPWD', 'G5RKRG', 'G5RJDR', 'G5DTW', 'G5DTU']
                        delSQLstr += "g5dze_test;"
         
                    rdbase.executeSQL(delSQLstr)
         
         
                #nazwy kolumn muszą zostać podane dokładnie jak w bazie - czyli małymi literami
                #na przyszłość można to rozwiązać w samej RobDBTable
                #za zamianę liter na małe w tablicy odpowiada ta fikuśna konstrukcja: [x.lower() ....]
                for tableName in tableList:
                    if import_testowy:
                        appendix = '_TEST'
                    else:
                        appendix = ''
                    rdg5Table[tableName] = RobDBTable(rdbase, tableName + appendix, [x.lower() for x in g5Cols[tableName]], 1, 1)
         
                G5Table = ""
         
                collist = []
                valuelist = []
                insertdic = {} # forma [nazwa_tabeli:ilosc_insertow] 
                arraylist = [] #wykorzystywana do przechowywania kolumn typu tablicaowego w formie [[col2, wart..], [col1, wart..], [col2, wart..]]
                arrayvalue = [] # wykorzystywane do przechowywania danych 1+ takich jak g5rkrg
                arrayname = '' # nazwa tablicy tożsama z nazwą kolumny w bazie
                pointslist = []
                point = []
                Kznak = ""  #znacznik + albo -, oznaczajacy czy okreslane sa punkty tworzace polygon czy
                            #wycinajace w nim dziure
                oldKznak = "0" #posluzy do sprawdzenia czy nastapila zmiana Kznak
                newPoly = 0
                polycount = 0
         
            
                linianr = 0     #przyda sie w momencie gdy sie program wywali - okresli ktora linia pliku swde nabroiła
                obieg = 0       #bedzie wykorzystywane przy commit do bazy, ktore bedzie realizowane co np 100 pytań SQL
                
                transform = False
                if import_testowy == False: #tylko jesli nie jest to import testowy
                    if pyproj4strFrom != pyproj4strTo:
                        transform = True
           
         
                self.dlg.peditOutput.appendPlainText( "Krok 2. Start procedury importowej: " + time.strftime("%Y-%m-%d %H:%M:%S"))
         
         
                if rodz_importu == 'aktualizacja':
                    #usuniecie wszystkich rekordow o id_zd
                    self.dlg.peditOutput.appendPlainText( u"Usuwanie rekordów ze zbioru danych o id =  " + uni(id_jed_rej))
                    self.dlg.peditOutput.appendPlainText( u"Rozpoczęcie usuwania aktualizowanych rekordów: " +  time.strftime("%Y-%m-%d %H:%M:%S"))
                    QApplication.processEvents()
                    rdbase.executeSQL("SELECT g5sp_delfromtables('" + id_jed_rej + "');")
                    self.dlg.peditOutput.appendPlainText( u"Zakończono usuwanie aktualizowanych rekordów: " +  time.strftime("%Y-%m-%d %H:%M:%S"))
                    QApplication.processEvents()
         
                try:
                    f.seek(0.0)
                    tekstline = ""
                    try:
                        self.dlg.peditOutput.appendPlainText(u"Krok 3. Rozpoczynam import: " + time.strftime("%Y-%m-%d %H:%M:%S"))
                        QApplication.processEvents()
                                                   
                        i = 0;
                        procent_wykonania = 0; #do monitorowania postepu
                        linianr = 0
                        step = ilosc_linii/100
                        
                        self.dlg.peditOutput.appendPlainText("Wykonano procent:")
                        self.dlg.peditOutput.appendPlainText("0")
                        for line in f.readlines():
                            tekstline = line #zmienna tekstline bedzie wykorzystywana poza petla w celu lokalizacji bledu - w exception
                            if i == step:
                                i = 0
                                procent_wykonania += 1
                                curs = self.dlg.peditOutput.textCursor()
                                curs.clearSelection()
                                curs.movePosition(QTextCursor.PreviousWord, QTextCursor.KeepAnchor)
                                curs.insertText(str(procent_wykonania))
                                QApplication.processEvents()
                                
                            
                            line = unicode(line, txtcodec)
                            #print "unikod zadzialal"
                            i= i + 1
                            linianr+=1 #przyda sie jak sie program wypierniczy
         
                            pocz = StringBetweenChar(line, ',',0)
         
                            if pocz == "RO" or pocz == "RD" or pocz == "RC":
                                #line = unicode(line, txtcodec)
                                G5Table =  StringBetweenChar(line, ',',2)
                                if G5Table == 'G5G_DZE' or G5Table == 'G5O_DZE':
                                    G5Table = 'G5DZE'
                                g5id1_value = StringBetweenChar(line,',',3)
                                g5id2_value = StringBetweenChar(line,',',4)
                            if line[0:3] == "P,P":
                                #self.dlg.peditOutput.appendPlainText(u"znaleziono ciąg line 0:3 = P,P")
                                str1 =  StringBetweenChar(line, ',', 2)
                                #self.dlg.peditOutput.appendPlainText(u"str1 = " + str1 + u" o długości " + str(len(str1)) )
                                if str1 == u"G5PZG":
                                    #self.dlg.peditOutput.appendPlainText(u"wlazło")
                                    nr =  StringBetweenChar(line, ',', 3)
                                    #self.dlg.peditOutput.appendPlainText(u"nr = " + nr)
                                    #strnr = nr.rstrip(';\r')# trzeba usuwac pojedynczo czyli tak jak poniżej
                                    strnr = nr.rstrip()# czyli jakiekolwiek białe znaki niezaleznie czy \n \r itp
                                    strnr = strnr.rstrip(';')
                                    #self.dlg.peditOutput.appendPlainText(u"strnr = " + strnr)
                                    #oldline = line
                                    #self.dlg.peditOutput.appendPlainText(u"oldline = " + oldline)
                                    
                                    #zdazaja sie sytuacje, ze w pliku swd nie bedzie zdefiniowanego punktu pzg dla
                                    #numeru podanego w definicji punktu. Troche to toporne ale w tym przypadku 
                                    if pzgdic.has_key(strnr):
                                        line = "P,G," + pzgdic[strnr] + ",;\n"
                                    else:
                                        line = "P,brakPZG"
                                    
                                    #self.dlg.peditOutput.appendPlainText(u"line = " + line)
                                    #self.dlg.peditOutput.appendPlainText(u"Zastąpiono ciąg P,P >>" + oldline + "<< na >>" + line + "<< " + strftime("%Y-%m-%d %H:%M:%S"))
         
    
                            if G5Table in tableList:
                                colname = ""
                                colvalue = ""
                                znacznik = StringBetweenChar(line, ',',0)
                                if znacznik == "D" or znacznik == "WG":
                                    line = line.rstrip()
                                    line = line.rstrip(';') # szczególnie linie ze znacznikami WG zakończone są średnikiem 
                                    line = line.strip("'")
                                    line = line.strip('"')
                                    line = line.replace("'", '')
                                    line = line.replace('"', "")
                                    colname = StringBetweenChar(line,',',1)
                                    #zamiana nazw kolumn z polskimi znakami
                                    if colname in plcharCols:
                                        colname = plcharCols[colname] 
                                    colvalue = StringBetweenChar(line,',',3)
                                    #dzialania wspolne dla wszystkich tablic
                                    if colname in g5Cols[G5Table]:
                                        #sprawdzenie czy wartosc colvalue nie przekracza maksymelnej dlugosci pola przewidzianego w bazie
                                        if colsLen[G5Table].has_key(colname):
                                            if len(colvalue) > colsLen[G5Table][colname]:
                                                oldcolvalue = colvalue
                                                colvalue = colvalue[0:colsLen[G5Table][colname]]
                                                self.dlg.peditOutput.appendPlainText( u"blablabla - old: " + oldcolvalue + '##### new: ' + colvalue ) 

                                        #G5RDZE w G5KLU nie jest typu tablicowego, natomiast w g5BUD
                                        #jest. Na szczescie w g5klu nie ma żadnego pola tablicowego
                                        #to samo dotyczy g5radr - w g5osf i g5ins - nie jest array w przeciwienstwie do g5bud
                                        if colname in arrayCols and G5Table != 'G5KLU' and G5Table != 'G5INS' and G5Table != 'G5OSF':
                                            arraylist.append([colname,colvalue])
         
                                        else:
                                            collist.append(colname)
                                            valuelist.append(colvalue)
         
                                        #dzialania nietypowe
                                        
                                        #TODO przewidziec dla g5obr wyluskanie numeru obrebu do osobnego pola
                                        if colname == 'G5IDD' and G5Table == "G5DZE": #trzeba wyluskac numer dzialki i zapisac do oddzielnej kolumny
                                            #nr_dzialki = StringBetweenChar(colvalue, '.', 2)
											# zmiana 08-01-2016 - zazwyczaj numer wystepuje po drugiej kropce, bo g5idd to 
											#zazwyczaj teryt, ale niestety sa wyjatki i po numerze obrebu czasem wystepuje
											#jeszcze jakis ciag znakow i dopiero potem nr dzialki. dlatego trzeba wyszukac
											#pozycje ostatniej kropki 
                                            collist.append(u'nr')
                                            valuelist.append(StringBetweenChar(colvalue, '.', colvalue.count(".")))
                                            #nr obrębu też się przyda
                                            collist.append(u'nrobr')
                                            valuelist.append(StringBetweenChar(colvalue, '.', 1))

                                            #zapamietanie wartosci g5idd - moze sie przydac do updata
                                            dze_g5idd = colvalue
         
         
                                        if colname == 'G5RPOD': #dla tabel g5udz i g5udw - wyglada to nastepujaco: "WG,G5RPOD,G5OSF,5465;"
                                                                #a więc najpierw mamy określenie do jakiej tabeli jest dowiązanie (osf, ins, mlz czy osz)
                                                                #a potem wartość wiązania w danej tabeli. Należy więc jeszcze wyciągnąć wartość po drugim ','
                                            collist.append(u'rpod_rodzaj')
                                            pod_rodzaj = StringBetweenChar(line, ',', 2)
                                            valuelist.append(pod_rodzaj)
                                            #kolumna zawierajaca polaczone ze soba wartosci 
                                            collist.append(u'id_podmiot')
                                            valuelist.append(colvalue + pod_rodzaj)
                                     
         
                                elif znacznik == "K":
                                    Kznak = StringBetweenChar(line, ',',1)#czyli albo '+;' albo '-;'
                                    Kznak = Kznak[0]#pozostawienie tylko + albo -
                                    newPoly = 1
                                    polycount+=1
                                    
                                elif znacznik == "P":
                                    if StringBetweenChar(line, ',',1) != 'brakPZG':
                                        yvalue = StringBetweenChar(line, ',',2)
                                        xvalue = StringBetweenChar(line, ',',3)
                                        #jezeli bedzie cos walniete w pliku swde to program sie moze wywalic
                                        #ponizej nastapi zamiana na wartosc liczbowa 0.0 - lepiej zaimportowac plik
                                        #z bledami niz nie zaimportowac wcale, bledy te bedzie latwo wylapac w qgisie
                                        #i poprawic
                                        if czyLiczba(yvalue) == False:
                                            yvalue = '0.0'
                                        if czyLiczba(xvalue) == False:
                                            xvalue = '0.0'
                                        #print "xv:", xvalue, "yv:", yvalue
                                        if transform:
                                            pt1 = xform.transform(QgsPoint(float(xvalue), float(yvalue)))
                                            value = str(pt1[0]) + " " + str(pt1[1])
                                        else:
                                            value = xvalue + " " + yvalue
                                        point.append( polycount)
                                        point.append(newPoly)
                                        point.append(Kznak)
                                        point.append(value) 
                                        pointslist.append(point)

                                        point = []
                                        newPoly = 0
         
                                elif znacznik[0] == "X": #czyli koniec definicji recordu
                                    #print "2 line", line
                                    #print "2 znacznik = ", znacznik, collist, valuelist
                                    p = ""
                                    p1 = ""
                                    if len(pointslist)>0:
                                        for points in pointslist:
                                            if points[1] == 1:#newPoly
                                                #p1 = points[3]
                                                if points[0] == 1:#czyli pierwszy i byc moze jedyny polygon
                                                    if srid == -1: #niezdefiniowany układ
                                                        p = "POLYGON(("
                                                    else:
                                                        p = "@ST_GeomFromText(\'POLYGON(("
                                                else: #czyli ewentualne kolejne polygony
                                                    p = p + p1 + "),("
                                                p1 = points[3]
                                            p = p + points[3] + ','
                                        if srid == -1:
                                            p = p + p1 + "))"
                                        else:
                                            p = p + p1 + "))\'," + srid + ")"
                                        collist.append("geom")
                                        valuelist.append(p)
         
                                    #dodanie kolumn tablicowych
                                    if len(arraylist) > 0:
                                        old_col = ''
                                        arraystr = "ARRAY["
                                        arraylist.sort()
                                        for col, val in arraylist:
                                            if old_col == '': #startujemy
                                                old_col = col
                                            if  col == old_col:
                                                arraystr += "\'"+ val + "\',"
                                            else: #nastąpiła zmiana columny
                                                arraystr = arraystr.rstrip(",")
                                                arraystr += "]"
                                                collist.append(old_col)
                                                valuelist.append(arraystr)
                                                old_col = col
                                                arraystr = "ARRAY[\'" + val + "\',"
                                        collist.append(old_col)
                                        arraystr = arraystr.rstrip(",")
                                        arraystr += ']'
                                        valuelist.append(arraystr)
                                        arraylist = []
         
                                    #dodatnie self.id_jed_rej do kazdej tabeli
                                    collist.append("id_zd")
                                    valuelist.append(id_jed_rej)
                                    #dodanie id1 i id2 do kazdej z tabel
                                    collist.append("g5id1")
                                    valuelist.append(g5id1_value)
                                    collist.append("g5id2")
                                    valuelist.append(g5id2_value)
                                    #dodanie unikatowej kolumny - będzie stanowiła klucz główny w całej bazie
                                    collist.append('tab_uid')
                                    valuelist.append(id_jed_rej+g5id1_value)
                                    #dodanie daty pliku swde do tabeli g5jew
                                    if G5Table == "G5JEW":
                                        collist.append(u'plik_data')
                                        valuelist.append(self.plik_data)

         
                                    #sprawdzenie czy jest jeszcze jakas tablica, ktora nie zostala dodana do valuelist
                                    if len(arrayvalue)>0:
                                        collist.append(arrayname)
                                        values = ""
                                        for value in arrayvalue:
                                            values += "\'" + value.strip('[]') + "\',"
                                        values = values.rstrip(",")#usuniecie ostatniego przecinka
                                        valuelist.append(u"ARRAY[" + values + "]")
                                        arrayname = ''
                                        arrayvalue = []

                                    #wstawienie danych do tabeli
                                    
                                    if uz_opis and (G5Table == 'G5DZE' or G5Table == 'G5DOK'):
                                        if G5Table == 'G5DZE':
                                            #self.dlg.peditOutput.appendPlainText(G5Table, dze_g5idd)
                                            rdg5Table[G5Table].update_where(collist, valuelist, ['id_zd', 'g5idd'], [id_jed_rej, dze_g5idd])
                                        
                                    else:
                                        rdg5Table[G5Table].insert(0, collist, valuelist)


                                    if G5Table in insertdic:
                                        insertdic[G5Table] += 1
                                    else:
                                        insertdic[G5Table] = 1
         
                                    #obieg+=1
                                    #if obieg == 1000:
                                    #    rdbase.commit()
                                    #    obieg = 0
                                    obieg+=1
                                    collist = []
                                    valuelist = []
                                    pointslist = []
                                    Kznak = ""
                                    polycount = 0
                                    G5Table = ""
         
                                    if rodz_importu == 'testowyJEW':
                                        #w tym przypadku nie ma co dalej ciągnąć pętli
                                        break
                            #i = i+1
                    except Exception, ex:
                        cols = "["
                        values = "["
                        for col in collist:
                            cols +=  col + ", "
                        for value in valuelist:
                            values += value + ", "
                        cols += "]"
                        values += "]"
                        self.dlg.peditOutput.appendPlainText( u"błąd--: " + uni(G5Table) +  uni(cols) + uni(values) + "rekord nr: " + uni(str(obieg)) + "line = " +  uni(tekstline) + "error: " + uni(str(ex)))
         
                    finally:
                        
                        rdbase.commit()
                        insstr = ""
                        for tab, ilosc in insertdic.items():
                            insstr += tab + ':' + str(ilosc) + '; '
                            
                        self.dlg.peditOutput.appendPlainText( "zapisano do bazy: " + str(obieg) + u" rekordów: " + insstr)
                             
                    
                        f.close()
                 
                except IOError:
                    self.dlg.peditOutput.appendPlainText( "IOError: " +  time.strftime("%Y-%m-%d %H:%M:%S"))
         
                self.dlg.peditOutput.appendPlainText( "przerobiono lini: " +  str(linianr))
                self.dlg.peditOutput.appendPlainText( "Koniec programu: " +  time.strftime("%Y-%m-%d %H:%M:%S"))
        
        except IOError:
                    self.dlg.peditOutput.appendPlainText( "IOError: ",  time.strftime("%Y-%m-%d %H:%M:%S"))   
#-------------------------------------------------------------------------------#   
    def tbtnOgr2ogrFileClicked(self):
        QMessageBox.information(self.dlg, "Uwaga!!!", u"Nie znaleziono identyfikatora jednostki rejestrowej - musisz samodzielnie określić identyfikator zbioru danych, wpisując samodzielnie - litery i cyfry - najlepiej do 10 znaków. Nie używaj polskich liter")
        
                

############################################################################# 
###          funkcje pomocnicze klasy SWDEImport2                         ###
############################################################################# 
    def txtCodec(self):
        if self.dlg.rdbtnKodowanieISO.isChecked():
            return  'iso8859_2'
        elif self.dlg.rdbtnKodowanieWindows.isChecked():
            return 'cp1250'
        elif self.dlg.rdbtnKodowanieUTF.isChecked():
            return 'utf-8'                     
############################################################################# 
###                     funkcje pomocnicze ogólne                         ###
#############################################################################
               
def StringBetweenChar(string, char, nr):
    #wyszukuje lancuch znakow pomiedzy okreslonymi w char znakami
    #nr - okresla pomiedzy ktorym (pierwszym) wystapieniem znaku
    #a kolejnym znajduje sie szukany ciag. Jesli nr okresla ostatnie
    #wystapienie znaku char w string-u zostanie wyszukany ciag do konca
    #stringa
    char_pos = -1 #pozycja znaku w ciagu
    char_wyst = 0 # kolejne wystapienie char w ciagu
    char_nextpos = -1 # pozycja kolejnego wystapienia znaku w ciagu

    if nr == 0: #czyli od poczatku stringa do pierwszego znaku
        char_pos = 0
        i = 0
        for ch in string:
            if ch  == char:
                char_nextpos = i
                break
            i = i + 1
    else:
        i = 0
        for ch in string:
            if ch == char:
                char_wyst = char_wyst + 1
                if char_wyst == nr:
                    char_pos = i + 1
                elif char_wyst == nr+1:
                    char_nextpos = i
                    break
            i = i + 1

    if char_pos != -1: #czyli znaleziono znak
        if char_nextpos == -1: #czyli trzeba czytac do konca linii
            char_nextpos = len(string)
        return  string[char_pos:char_nextpos]
    else:
        return -1
#-----------------------------------------------------------------
def czyLiczba(l):
    a = 0
    try:
        float(l)
        a = True
    except ValueError:
        a = False
    return a
