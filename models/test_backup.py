import json
import logging
import os
import requests
import tempfile
import odoo
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.service import db

_logger = logging.getLogger(__name__)
class BackupConfigure(models.Model):
    _name = 'backup.configure'
    _inherit='mail.thread'
    _description = 'Automatic Database Backup'

    name = fields.Char(string='Name', required=True, help='Add the name')
    db_name = fields.Char(string='Database Name', required=True,
                          help='Name of the database')
    master_pwd = fields.Char(string='Master Password', required=True,
                             help='Master password')
    backup_format = fields.Selection([
        ('zip', 'Zip'),
        ('dump', 'Dump')
       ], string='Backup Format', default='zip', required=True,
        help='Format of the backup')
    backup_destination = fields.Selection([
        ('local', 'Local Storage')], string='Backup Destination', help='Destination of the backup')
    backup_path = fields.Char(string='Backup Path',
                              help='Local storage directory path')
    active = fields.Boolean(default=False, string='Active',
                            help='Activate the Scheduled Action or not')
    hide_active = fields.Boolean(string="Hide Active",
                                 help="Make active field to readonly")
    auto_remove = fields.Boolean(string='Remove Old Backups',
                                 help='Remove old backups')
    days_to_remove = fields.Integer(string='Remove After',
                                    help='Automatically delete stored backups'
                                         ' after this specified number of days')
    backup_filename = fields.Char(string='Backup Filename',
                                  help='For Storing generated backup filename')
    notify_user = fields.Boolean(string='Notify User',
                                 help='Send an email notification to user when'
                                      'the backup operation is successful'
                                      'or failed')
    user_id = fields.Many2one('res.users', string='User',
                              help='Name of the user')
    generated_exception = fields.Char(string='Exception',
                                      help='Exception Encountered while Backup'
                                           'generation')
    
    def _onchange_back_up_local(self):
        """
        On change handler for the 'backup_destination' field. This method is
        triggered when the value of 'backup_destination' is changed. If the
        chosen backup destination is 'local', it sets the 'hide_active' field
        to True which make active field to readonly to False.
         """
        if self.backup_destination == 'local':
            self.hide_active = True
    
    def _schedule_auto_backup(self):
        """Function for generating and storing backup.
           Database backup for all the active records in backup configuration
           model will be created."""
        records = self.search([])
        mail_template_success = self.env.ref(
            'test_backup.mail_template_data_db_backup_successful')
        mail_template_failed = self.env.ref(
            'test_backup.mail_template_data_db_backup_failed')
        for rec in records:
            backup_time = fields.datetime.utcnow().strftime(
                "%Y-%m-%d_%H-%M-%S")
            backup_filename = "%s_%s.%s" % (
                rec.db_name, backup_time, rec.backup_format)
            rec.backup_filename = backup_filename
            # Local backup
            if rec.backup_destination == 'local':
                try:
                    if not os.path.isdir(rec.backup_path):
                        os.makedirs(rec.backup_path)
                    backup_file = os.path.join(rec.backup_path,
                                               backup_filename)
                    f = open(backup_file, "wb")
                    odoo.service.db.dump_db(rec.db_name, f, rec.backup_format)
                    f.close()
                    # Remove older backups
                    if rec.auto_remove:
                        for filename in os.listdir(rec.backup_path):
                            file = os.path.join(rec.backup_path, filename)
                            create_time = fields.datetime.fromtimestamp(
                                os.path.getctime(file))
                            backup_duration = fields.datetime.utcnow() - create_time
                            if backup_duration.days >= rec.days_to_remove:
                                os.remove(file)
                    if rec.notify_user:
                        mail_template_success.send_mail(rec.id,
                                                        force_send=True)
                except Exception as e:
                    rec.generated_exception = e
                    _logger.info('FTP Exception: %s', e)
                    if rec.notify_user:
                        mail_template_failed.send_mail(rec.id, force_send=True)


