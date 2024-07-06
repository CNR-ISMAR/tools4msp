from tools4msp.models import CaseStudyRun


def set_runstatus(task):
    run_result = task.result
    csr_id = run_result['csr_id']
    csr = CaseStudyRun.objects.get(id=csr_id)
    if run_result['error'] is None:
        csr.runstatus = 1
    else:
        csr.runstatus = 2
        csr.runerror = run_result['error']
    csr.save()
